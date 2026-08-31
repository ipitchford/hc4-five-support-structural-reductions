#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include <givaro/modular.h>
#include <linbox/matrix/sparse-matrix.h>
#include <linbox/solutions/solve.h>
#include <linbox/vector/blas-vector.h>

namespace {

using Field = Givaro::Modular<std::uint64_t>;
using Matrix = LinBox::SparseMatrix<Field, LinBox::SparseMatrixFormat::SparseSeq>;
using Vector = LinBox::BlasVector<Field>;
using Clock = std::chrono::steady_clock;

struct Arguments {
    bool toy = false;
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
        if (item == "--toy") {
            result.toy = true;
        } else if (item == "--csr" && index + 1 < argc) {
            result.csr_path = argv[++index];
        } else if (item == "--rhs" && index + 1 < argc) {
            result.rhs_path = argv[++index];
        } else if (item == "--solution-output" && index + 1 < argc) {
            result.solution_path = argv[++index];
        } else {
            throw std::runtime_error("unsupported or incomplete argument: " + item);
        }
    }
    if (result.solution_path.empty()) throw std::runtime_error("--solution-output is required");
    if (result.toy == !result.csr_path.empty()) throw std::runtime_error("choose exactly one of --toy or --csr");
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

void load_csr(const Field& field, const std::string& path, Matrix& matrix,
              std::uint64_t expected_rows, std::uint64_t expected_columns,
              std::uint64_t expected_nonzeros) {
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
    for (std::uint64_t row = 0; row < rows; ++row) {
        std::uint32_t previous = 0;
        bool has_previous = false;
        for (std::uint64_t position = offsets[row]; position < offsets[row + 1]; ++position) {
            const auto column = column_indices[position];
            if (column >= columns || (has_previous && column <= previous))
                throw std::runtime_error("CSR row column order mismatch");
            if (values[position] == 0 || values[position] >= 181)
                throw std::runtime_error("CSR value outside nonzero GF(181) residues");
            set_residue(field, value, values[position]);
            matrix.setEntry(row, column, value);
            previous = column;
            has_previous = true;
        }
    }
}

void load_rhs(const Field& field, const std::string& path, Vector& rhs) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open RHS input");
    std::vector<std::uint8_t> values(rhs.size());
    input.read(reinterpret_cast<char*>(values.data()), static_cast<std::streamsize>(values.size()));
    if (!input || input.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("RHS length mismatch");
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (values[index] >= 181) throw std::runtime_error("RHS residue outside GF(181)");
        set_residue(field, rhs[index], values[index]);
    }
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
        const std::uint64_t columns = arguments.toy ? 3 : 35881;
        const std::uint64_t nonzeros = arguments.toy ? 9 : 1354540;
        const auto total_started = Clock::now();
        const auto load_started = Clock::now();
        Matrix coefficient(field, rows, columns);
        if (arguments.toy) load_toy(field, coefficient);
        else load_csr(field, arguments.csr_path, coefficient, rows, columns, nonzeros);
        const double load_seconds = seconds_since(load_started);

        Vector known(field, columns);
        Vector rhs(field, rows);
        const bool synthetic = arguments.rhs_path.empty();
        if (synthetic) {
            for (std::uint64_t column = 0; column < columns; ++column)
                set_residue(field, known[column], ((column + 1) * 37 + 11) % 180 + 1);
            coefficient.apply(rhs, known);
        } else {
            load_rhs(field, arguments.rhs_path, rhs);
        }

        Vector solution(field, columns);
        const auto solve_started = Clock::now();
        LinBox::solve(solution, coefficient, rhs, LinBox::Method::SparseElimination());
        const double solve_seconds = seconds_since(solve_started);

        Vector replay(field, rows);
        const auto replay_started = Clock::now();
        coefficient.apply(replay, solution);
        std::uint64_t replay_mismatches = 0;
        for (std::uint64_t row = 0; row < rows; ++row)
            if (!field.areEqual(replay[row], rhs[row])) ++replay_mismatches;
        std::uint64_t known_mismatches = 0;
        if (synthetic)
            for (std::uint64_t column = 0; column < columns; ++column)
                if (!field.areEqual(solution[column], known[column])) ++known_mismatches;
        const double replay_seconds = seconds_since(replay_started);
        write_vector(field, solution, arguments.solution_path);

        const bool passed = replay_mismatches == 0 && (!synthetic || known_mismatches == 0);
        std::cout << "{\"status\":\"" << (passed ? "PASS_LINBOX_SPARSE_MOD181_EXPLICIT_SOLVE" : "FAIL_LINBOX_SPARSE_MOD181_EXPLICIT_SOLVE")
                  << "\",\"mode\":\"" << (synthetic ? "synthetic_known_solution" : "external_rhs")
                  << "\",\"rows\":" << rows << ",\"columns\":" << columns
                  << ",\"nonzeros\":" << nonzeros
                  << ",\"load_seconds\":" << load_seconds
                  << ",\"solve_seconds\":" << solve_seconds
                  << ",\"replay_seconds\":" << replay_seconds
                  << ",\"replay_mismatches\":" << replay_mismatches
                  << ",\"known_solution_mismatches\":" << known_mismatches
                  << ",\"wall_seconds\":" << seconds_since(total_started) << "}" << std::endl;
        return passed ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "linbox_sparse_mod181_solve_driver: " << error.what() << std::endl;
        return 2;
    }
}
