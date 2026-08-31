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

struct Arguments {
    bool toy = false;
    std::string csr_path;
    std::string solution_path;
    std::uint64_t columns = 0;
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
        if (item == "--toy") {
            result.toy = true;
        } else if (item == "--csr" && index + 1 < argc) {
            result.csr_path = argv[++index];
        } else if (item == "--solution-output" && index + 1 < argc) {
            result.solution_path = argv[++index];
        } else if (item == "--columns" && index + 1 < argc) {
            result.columns = std::stoull(argv[++index]);
        } else {
            throw std::runtime_error("unsupported or incomplete argument: " + item);
        }
    }
    if (result.solution_path.empty()) throw std::runtime_error("--solution-output is required");
    if (result.toy == !result.csr_path.empty()) throw std::runtime_error("choose exactly one of --toy or --csr");
    if (result.toy && result.columns != 0) throw std::runtime_error("--columns is not permitted with --toy");
    if (!result.toy && result.columns == 0) result.columns = 35881;
    if (!result.toy && (result.columns > 35881 || result.columns == 0))
        throw std::runtime_error("--columns outside 1..35881");
    return result;
}

void set_residue(const Field& field, Field::Element& output, std::uint64_t value) {
    field.init(output, value % 181);
}

std::uint8_t residue(const Field& field, const Field::Element& value) {
    std::uint64_t output = 0;
    field.convert(output, value);
    if (output >= 181) throw std::runtime_error("noncanonical field residue");
    return static_cast<std::uint8_t>(output);
}

void load_toy(const Field& field, Matrix& matrix) {
    const std::uint64_t entries[][3] = {
        {0, 0, 1}, {1, 1, 1}, {2, 2, 1},
        {3, 0, 2}, {3, 1, 3}, {3, 2, 5},
        {4, 0, 7}, {4, 1, 11}, {4, 2, 13},
    };
    Field::Element value;
    field.init(value);
    for (const auto& entry : entries) {
        set_residue(field, value, entry[2]);
        matrix.setEntry(entry[0], entry[1], value);
    }
}

std::uint64_t load_csr_prefix(const Field& field, const std::string& path, Matrix& matrix,
                              std::uint64_t selected_columns) {
    constexpr std::uint64_t expected_rows = 85651;
    constexpr std::uint64_t expected_columns = 35881;
    constexpr std::uint64_t expected_nonzeros = 1354540;
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open CSR input");
    char magic[8];
    input.read(magic, 8);
    if (!input || std::memcmp(magic, "HC4AC181", 8) != 0) throw std::runtime_error("CSR magic mismatch");
    const auto rows = read_u64(input);
    const auto columns = read_u64(input);
    const auto nonzeros = read_u64(input);
    if (rows != expected_rows || columns != expected_columns || nonzeros != expected_nonzeros)
        throw std::runtime_error("CSR dimension mismatch");
    std::vector<std::uint64_t> offsets(rows + 1);
    for (auto& value : offsets) value = read_u64(input);
    if (offsets.front() != 0 || offsets.back() != nonzeros)
        throw std::runtime_error("CSR offset boundary mismatch");
    for (std::size_t index = 1; index < offsets.size(); ++index)
        if (offsets[index] < offsets[index - 1]) throw std::runtime_error("CSR offsets not monotone");
    std::vector<std::uint32_t> column_indices(nonzeros);
    for (auto& value : column_indices) value = read_u32(input);
    std::vector<std::uint8_t> values(nonzeros);
    input.read(reinterpret_cast<char*>(values.data()), static_cast<std::streamsize>(values.size()));
    if (!input) throw std::runtime_error("truncated CSR values");
    if (input.peek() != std::char_traits<char>::eof()) throw std::runtime_error("CSR trailing bytes");
    Field::Element value;
    field.init(value);
    std::uint64_t loaded = 0;
    for (std::uint64_t row = 0; row < rows; ++row) {
        std::uint32_t previous = 0;
        bool has_previous = false;
        for (std::uint64_t position = offsets[row]; position < offsets[row + 1]; ++position) {
            const auto column = column_indices[position];
            if (column >= columns || (has_previous && column <= previous))
                throw std::runtime_error("CSR row column order mismatch");
            if (values[position] == 0 || values[position] >= 181)
                throw std::runtime_error("CSR value outside nonzero GF(181) residues");
            if (column < selected_columns) {
                set_residue(field, value, values[position]);
                matrix.setEntry(row, column, value);
                ++loaded;
            }
            previous = column;
            has_previous = true;
        }
    }
    if (selected_columns == expected_columns && loaded != expected_nonzeros)
        throw std::runtime_error("full-prefix nonzero count mismatch");
    return loaded;
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
        const Field field(181);
        const std::uint64_t rows = arguments.toy ? 5 : 85651;
        const std::uint64_t columns = arguments.toy ? 3 : arguments.columns;
        const auto total_started = Clock::now();
        const auto load_started = Clock::now();
        Matrix coefficient(field, rows, columns);
        std::uint64_t nonzeros = 9;
        if (arguments.toy) load_toy(field, coefficient);
        else nonzeros = load_csr_prefix(field, arguments.csr_path, coefficient, columns);
        const double load_seconds = seconds_since(load_started);

        Vector known(field, columns);
        Vector rhs(field, rows);
        for (std::uint64_t column = 0; column < columns; ++column)
            set_residue(field, known[column], ((column + 1) * 37 + 11) % 180 + 1);
        coefficient.apply(rhs, known);

        const auto augmentation_started = Clock::now();
        Matrix augmented(field, rows, columns + 1);
        Field::Element rhs_value;
        field.init(rhs_value);
        for (std::uint64_t row = 0; row < rows; ++row) {
            augmented[row] = coefficient[row];
            if (!field.isZero(rhs[row])) {
                field.assign(rhs_value, rhs[row]);
                augmented.setEntry(row, columns, rhs_value);
            }
        }
        const double augmentation_seconds = seconds_since(augmentation_started);

        LinBox::BlasMatrix<Field> nullspace(field, columns + 1, 1);
        LinBox::GaussDomain<Field> gauss(field);
        const auto solve_started = Clock::now();
        gauss.nullspacebasisin(nullspace, augmented);
        const double solve_seconds = seconds_since(solve_started);
        if (nullspace.rowdim() != columns + 1 || nullspace.coldim() != 1)
            throw std::runtime_error("augmented nullity is not exactly one");
        const auto& last = nullspace.getEntry(columns, 0);
        if (field.isZero(last)) throw std::runtime_error("null vector has zero augmented coordinate");

        Field::Element inverse_last;
        field.init(inverse_last);
        field.inv(inverse_last, last);
        Vector solution(field, columns);
        for (std::uint64_t column = 0; column < columns; ++column) {
            field.mul(solution[column], nullspace.getEntry(column, 0), inverse_last);
            field.negin(solution[column]);
        }

        Vector replay(field, rows);
        const auto replay_started = Clock::now();
        coefficient.apply(replay, solution);
        std::uint64_t replay_mismatches = 0;
        for (std::uint64_t row = 0; row < rows; ++row)
            if (!field.areEqual(replay[row], rhs[row])) ++replay_mismatches;
        std::uint64_t known_mismatches = 0;
        for (std::uint64_t column = 0; column < columns; ++column)
            if (!field.areEqual(solution[column], known[column])) ++known_mismatches;
        const double replay_seconds = seconds_since(replay_started);
        write_vector(field, solution, arguments.solution_path);

        const bool passed = replay_mismatches == 0 && known_mismatches == 0;
        std::cout << "{\"status\":\"" << (passed ? "PASS_LINBOX_AUGMENTED_NULLSPACE_MOD181_SYNTHETIC_SOLVE" : "FAIL_LINBOX_AUGMENTED_NULLSPACE_MOD181_SYNTHETIC_SOLVE")
                  << "\",\"mode\":\"synthetic_known_solution\""
                  << ",\"rows\":" << rows << ",\"columns\":" << columns
                  << ",\"coefficient_nonzeros\":" << nonzeros
                  << ",\"load_seconds\":" << load_seconds
                  << ",\"augmentation_seconds\":" << augmentation_seconds
                  << ",\"nullspace_seconds\":" << solve_seconds
                  << ",\"replay_seconds\":" << replay_seconds
                  << ",\"replay_mismatches\":" << replay_mismatches
                  << ",\"known_solution_mismatches\":" << known_mismatches
                  << ",\"last_null_coordinate\":" << static_cast<unsigned>(residue(field, last))
                  << ",\"wall_seconds\":" << seconds_since(total_started) << "}" << std::endl;
        return passed ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "linbox_augmented_nullspace_mod181_solve_driver: " << error.what() << std::endl;
        return 2;
    }
}
