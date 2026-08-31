#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include <givaro/modular.h>
#include <linbox/algorithms/gauss.h>
#include <linbox/matrix/dense-matrix.h>
#include <linbox/matrix/sparse-matrix.h>
#include <linbox/vector/blas-vector.h>

namespace {

using Field = Givaro::Modular<std::uint64_t>;
using Matrix = LinBox::SparseMatrix<Field, LinBox::SparseMatrixFormat::SparseSeq>;
using Vector = LinBox::BlasVector<Field>;
using Clock = std::chrono::steady_clock;

constexpr std::uint64_t kPrime = 173;
constexpr std::uint64_t kRows = 85688;
constexpr std::uint64_t kColumns = 36587;
constexpr std::uint64_t kNonzeros = 1487624;

struct Arguments {
    std::string csr_path;
    std::string rhs_path;
    std::string solution_path;
};

double seconds_since(const Clock::time_point& start) {
    return std::chrono::duration<double>(Clock::now() - start).count();
}

std::uint64_t read_u64(std::istream& input) {
    std::uint8_t bytes[8];
    input.read(reinterpret_cast<char*>(bytes), 8);
    if (!input) throw std::runtime_error("truncated u64");
    std::uint64_t value = 0;
    for (int index = 7; index >= 0; --index) value = (value << 8) | bytes[index];
    return value;
}

std::uint32_t read_u32(std::istream& input) {
    std::uint8_t bytes[4];
    input.read(reinterpret_cast<char*>(bytes), 4);
    if (!input) throw std::runtime_error("truncated u32");
    return static_cast<std::uint32_t>(bytes[0]) |
           (static_cast<std::uint32_t>(bytes[1]) << 8) |
           (static_cast<std::uint32_t>(bytes[2]) << 16) |
           (static_cast<std::uint32_t>(bytes[3]) << 24);
}

Arguments parse_arguments(int argc, char** argv) {
    Arguments result;
    for (int index = 1; index < argc; ++index) {
        const std::string item(argv[index]);
        if (item == "--csr" && index + 1 < argc) {
            result.csr_path = argv[++index];
        } else if (item == "--rhs" && index + 1 < argc) {
            result.rhs_path = argv[++index];
        } else if (item == "--solution-output" && index + 1 < argc) {
            result.solution_path = argv[++index];
        } else {
            throw std::runtime_error("unsupported or incomplete argument: " + item);
        }
    }
    if (result.csr_path.empty() || result.rhs_path.empty() || result.solution_path.empty())
        throw std::runtime_error("--csr, --rhs, and --solution-output are required");
    return result;
}

void set_residue(const Field& field, Field::Element& output, std::uint64_t value) {
    field.init(output, value % kPrime);
}

std::uint8_t residue(const Field& field, const Field::Element& value) {
    std::uint64_t output = 0;
    field.convert(output, value);
    if (output >= kPrime) throw std::runtime_error("noncanonical field residue");
    return static_cast<std::uint8_t>(output);
}

void load_csr(const Field& field, const std::string& path, Matrix& matrix) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open CSR input");
    char magic[8];
    input.read(magic, 8);
    if (!input || std::memcmp(magic, "HC4AC173", 8) != 0)
        throw std::runtime_error("CSR magic mismatch");
    const auto rows = read_u64(input);
    const auto columns = read_u64(input);
    const auto nonzeros = read_u64(input);
    if (rows != kRows || columns != kColumns || nonzeros != kNonzeros)
        throw std::runtime_error("CSR dimension mismatch");
    std::vector<std::uint64_t> offsets(rows + 1);
    for (auto& value : offsets) value = read_u64(input);
    if (offsets.front() != 0 || offsets.back() != nonzeros)
        throw std::runtime_error("CSR offset boundary mismatch");
    for (std::size_t index = 1; index < offsets.size(); ++index)
        if (offsets[index] < offsets[index - 1])
            throw std::runtime_error("CSR offsets not monotone");
    std::vector<std::uint32_t> column_indices(nonzeros);
    for (auto& value : column_indices) value = read_u32(input);
    std::vector<std::uint8_t> values(nonzeros);
    input.read(reinterpret_cast<char*>(values.data()), static_cast<std::streamsize>(values.size()));
    if (!input) throw std::runtime_error("truncated CSR values");
    if (input.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("CSR trailing bytes");
    Field::Element value;
    field.init(value);
    for (std::uint64_t row = 0; row < rows; ++row) {
        std::uint32_t previous = 0;
        bool has_previous = false;
        for (std::uint64_t position = offsets[row]; position < offsets[row + 1]; ++position) {
            const auto column = column_indices[position];
            if (column >= columns || (has_previous && column <= previous))
                throw std::runtime_error("CSR row column order mismatch");
            if (values[position] == 0 || values[position] >= kPrime)
                throw std::runtime_error("CSR value outside nonzero GF(173) residues");
            set_residue(field, value, values[position]);
            matrix.setEntry(row, column, value);
            previous = column;
            has_previous = true;
        }
    }
}

void load_rhs(const Field& field, const std::string& path, Vector& rhs) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) throw std::runtime_error("cannot open RHS input");
    if (input.tellg() != static_cast<std::streamoff>(kRows))
        throw std::runtime_error("RHS byte length mismatch");
    input.seekg(0);
    Field::Element value;
    field.init(value);
    for (std::uint64_t row = 0; row < kRows; ++row) {
        std::uint8_t byte = 0;
        input.read(reinterpret_cast<char*>(&byte), 1);
        if (!input || byte >= kPrime) throw std::runtime_error("RHS residue outside GF(173)");
        set_residue(field, value, byte);
        field.assign(rhs[row], value);
    }
    if (input.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("RHS trailing bytes");
}

void write_vector(const Field& field, const Vector& value, const std::string& path) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot open solution output");
    for (const auto& item : value) {
        const auto byte = residue(field, item);
        output.write(reinterpret_cast<const char*>(&byte), 1);
    }
    if (!output) throw std::runtime_error("failed writing solution output");
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto arguments = parse_arguments(argc, argv);
        const Field field(kPrime);
        const auto total_started = Clock::now();

        const auto load_started = Clock::now();
        Matrix coefficient(field, kRows, kColumns);
        Vector rhs(field, kRows);
        load_csr(field, arguments.csr_path, coefficient);
        load_rhs(field, arguments.rhs_path, rhs);
        const double load_seconds = seconds_since(load_started);

        const auto augmentation_started = Clock::now();
        Matrix augmented(field, kRows, kColumns + 1);
        Field::Element rhs_value;
        field.init(rhs_value);
        for (std::uint64_t row = 0; row < kRows; ++row) {
            augmented[row] = coefficient[row];
            if (!field.isZero(rhs[row])) {
                field.assign(rhs_value, rhs[row]);
                augmented.setEntry(row, kColumns, rhs_value);
            }
        }
        const double augmentation_seconds = seconds_since(augmentation_started);

        LinBox::BlasMatrix<Field> nullspace(field, kColumns + 1, 1);
        LinBox::GaussDomain<Field> gauss(field);
        const auto solve_started = Clock::now();
        gauss.nullspacebasisin(nullspace, augmented);
        const double solve_seconds = seconds_since(solve_started);
        const auto nullity = nullspace.coldim();
        if (nullspace.rowdim() != kColumns + 1)
            throw std::runtime_error("augmented nullspace row dimension changed");
        if (nullity == 0) {
            std::cout << "{\"status\":\"STOP_TARGET_OUTSIDE_COLUMN_SPACE_MOD173\""
                      << ",\"mode\":\"explicit_target\",\"rows\":" << kRows
                      << ",\"columns\":" << kColumns
                      << ",\"coefficient_nonzeros\":" << kNonzeros
                      << ",\"augmented_nullity\":0"
                      << ",\"load_seconds\":" << load_seconds
                      << ",\"augmentation_seconds\":" << augmentation_seconds
                      << ",\"nullspace_seconds\":" << solve_seconds
                      << ",\"wall_seconds\":" << seconds_since(total_started) << "}" << std::endl;
            return 4;
        }
        if (nullity != 1) throw std::runtime_error("augmented nullity exceeds one");
        const auto& last = nullspace.getEntry(kColumns, 0);
        if (field.isZero(last))
            throw std::runtime_error("null vector has zero augmented coordinate");

        Field::Element inverse_last;
        field.init(inverse_last);
        field.inv(inverse_last, last);
        Vector solution(field, kColumns);
        for (std::uint64_t column = 0; column < kColumns; ++column) {
            field.mul(solution[column], nullspace.getEntry(column, 0), inverse_last);
            field.negin(solution[column]);
        }

        Vector replay(field, kRows);
        const auto replay_started = Clock::now();
        coefficient.apply(replay, solution);
        std::uint64_t replay_mismatches = 0;
        for (std::uint64_t row = 0; row < kRows; ++row)
            if (!field.areEqual(replay[row], rhs[row])) ++replay_mismatches;
        const double replay_seconds = seconds_since(replay_started);
        write_vector(field, solution, arguments.solution_path);

        const bool passed = replay_mismatches == 0;
        std::cout << "{\"status\":\""
                  << (passed ? "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD173_EXPLICIT_TARGET_SOLVE"
                             : "FAIL_LINBOX_AUGMENTED_NULLSPACE_MOD173_EXPLICIT_TARGET_SOLVE")
                  << "\",\"mode\":\"explicit_target\""
                  << ",\"rows\":" << kRows << ",\"columns\":" << kColumns
                  << ",\"coefficient_nonzeros\":" << kNonzeros
                  << ",\"augmented_nullity\":" << nullity
                  << ",\"load_seconds\":" << load_seconds
                  << ",\"augmentation_seconds\":" << augmentation_seconds
                  << ",\"nullspace_seconds\":" << solve_seconds
                  << ",\"replay_seconds\":" << replay_seconds
                  << ",\"replay_mismatches\":" << replay_mismatches
                  << ",\"last_null_coordinate\":"
                  << static_cast<unsigned>(residue(field, last))
                  << ",\"wall_seconds\":" << seconds_since(total_started) << "}" << std::endl;
        return passed ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "linbox_augmented_nullspace_mod173_fourth_target_driver: " << error.what() << std::endl;
        return 2;
    }
}
