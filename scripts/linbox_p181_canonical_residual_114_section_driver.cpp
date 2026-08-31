#include <algorithm>
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

namespace {

using Field = Givaro::Modular<std::uint64_t>;
using Matrix = LinBox::SparseMatrix<Field, LinBox::SparseMatrixFormat::SparseSeq>;
using Clock = std::chrono::steady_clock;

constexpr std::uint64_t kPrime = 181;
constexpr std::uint64_t kRows = 85651;
constexpr std::uint64_t kColumns = 35881;
constexpr std::uint64_t kRhs = 114;
constexpr std::uint64_t kNonzeros = 1354540;

struct Arguments {
    bool toy = false;
    std::string csr_path;
    std::string rhs_path;
    std::string solution_path;
};

struct SparseData {
    std::vector<std::uint64_t> offsets;
    std::vector<std::uint32_t> columns;
    std::vector<std::uint8_t> values;
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
    if (result.toy) {
        if (!result.csr_path.empty() || !result.rhs_path.empty())
            throw std::runtime_error("--toy forbids --csr and --rhs");
    } else if (result.csr_path.empty() || result.rhs_path.empty()) {
        throw std::runtime_error("actual mode requires --csr and --rhs");
    }
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

SparseData load_actual(const Field& field, const std::string& path, Matrix& matrix) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open CSR input");
    char magic[8];
    input.read(magic, 8);
    if (!input || std::memcmp(magic, "HC4AC181", 8) != 0)
        throw std::runtime_error("CSR magic mismatch");
    const auto rows = read_u64(input);
    const auto columns = read_u64(input);
    const auto nonzeros = read_u64(input);
    if (rows != kRows || columns != kColumns || nonzeros != kNonzeros)
        throw std::runtime_error("CSR dimensions drift");
    SparseData data;
    data.offsets.resize(rows + 1);
    for (auto& value : data.offsets) value = read_u64(input);
    if (data.offsets.front() != 0 || data.offsets.back() != nonzeros)
        throw std::runtime_error("CSR offset boundary mismatch");
    data.columns.resize(nonzeros);
    for (auto& value : data.columns) value = read_u32(input);
    data.values.resize(nonzeros);
    input.read(reinterpret_cast<char*>(data.values.data()), static_cast<std::streamsize>(data.values.size()));
    if (!input || input.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("CSR value payload drift");
    Field::Element value;
    field.init(value);
    for (std::uint64_t row = 0; row < rows; ++row) {
        std::uint32_t previous = 0;
        bool has_previous = false;
        for (std::uint64_t position = data.offsets[row]; position < data.offsets[row + 1]; ++position) {
            const auto column = data.columns[position];
            const auto byte = data.values[position];
            if (column >= columns || (has_previous && column <= previous) || byte == 0 || byte >= kPrime)
                throw std::runtime_error("malformed CSR row");
            set_residue(field, value, byte);
            matrix.setEntry(row, column, value);
            previous = column;
            has_previous = true;
        }
    }
    return data;
}

SparseData load_toy(const Field& field, Matrix& matrix) {
    const std::uint64_t entries[][3] = {
        {0, 0, 1}, {1, 1, 1}, {2, 2, 1},
        {3, 0, 2}, {3, 1, 3}, {3, 2, 5},
        {4, 0, 7}, {4, 1, 11}, {4, 2, 13},
    };
    SparseData data;
    data.offsets = {0, 1, 2, 3, 6, 9};
    Field::Element value;
    field.init(value);
    for (const auto& entry : entries) {
        data.columns.push_back(static_cast<std::uint32_t>(entry[1]));
        data.values.push_back(static_cast<std::uint8_t>(entry[2]));
        set_residue(field, value, entry[2]);
        matrix.setEntry(entry[0], entry[1], value);
    }
    return data;
}

std::vector<std::uint8_t> load_rhs(const std::string& path, std::uint64_t rows, std::uint64_t rhs_count) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input) throw std::runtime_error("cannot open RHS input");
    const auto expected = static_cast<std::streamoff>(rows * rhs_count);
    if (input.tellg() != expected) throw std::runtime_error("RHS byte length mismatch");
    input.seekg(0);
    std::vector<std::uint8_t> rhs(static_cast<std::size_t>(expected));
    input.read(reinterpret_cast<char*>(rhs.data()), expected);
    if (!input || input.peek() != std::char_traits<char>::eof())
        throw std::runtime_error("RHS payload drift");
    for (const auto value : rhs)
        if (value >= kPrime) throw std::runtime_error("RHS value outside GF(181)");
    return rhs;
}

std::vector<std::uint8_t> toy_rhs(const SparseData& data) {
    constexpr std::uint64_t rows = 5;
    constexpr std::uint64_t columns = 3;
    constexpr std::uint64_t rhs_count = 2;
    const std::uint8_t known[columns][rhs_count] = {{1, 2}, {3, 4}, {5, 6}};
    std::vector<std::uint8_t> rhs(rows * rhs_count, 0);
    for (std::uint64_t row = 0; row < rows; ++row)
        for (std::uint64_t position = data.offsets[row]; position < data.offsets[row + 1]; ++position)
            for (std::uint64_t column = 0; column < rhs_count; ++column)
                rhs[row * rhs_count + column] = static_cast<std::uint8_t>(
                    (rhs[row * rhs_count + column] + data.values[position] * known[data.columns[position]][column]) % kPrime);
    return rhs;
}

std::uint16_t inverse_mod(std::uint16_t value) {
    int old_r = static_cast<int>(kPrime), r = value;
    int old_t = 0, t = 1;
    while (r != 0) {
        const int quotient = old_r / r;
        const int next_r = old_r - quotient * r;
        old_r = r;
        r = next_r;
        const int next_t = old_t - quotient * t;
        old_t = t;
        t = next_t;
    }
    if (old_r != 1) throw std::runtime_error("nonunit modular pivot");
    old_t %= static_cast<int>(kPrime);
    if (old_t < 0) old_t += static_cast<int>(kPrime);
    return static_cast<std::uint16_t>(old_t);
}

std::vector<std::uint16_t> invert_bottom(const std::vector<std::uint16_t>& bottom, std::uint64_t count) {
    std::vector<std::uint16_t> augmented(count * 2 * count, 0);
    const auto width = 2 * count;
    for (std::uint64_t row = 0; row < count; ++row) {
        for (std::uint64_t column = 0; column < count; ++column)
            augmented[row * width + column] = bottom[row * count + column];
        augmented[row * width + count + row] = 1;
    }
    for (std::uint64_t column = 0; column < count; ++column) {
        std::uint64_t pivot = column;
        while (pivot < count && augmented[pivot * width + column] == 0) ++pivot;
        if (pivot == count) throw std::runtime_error("nullspace bottom block is singular");
        if (pivot != column)
            for (std::uint64_t item = 0; item < width; ++item)
                std::swap(augmented[pivot * width + item], augmented[column * width + item]);
        const auto inverse = inverse_mod(augmented[column * width + column]);
        for (std::uint64_t item = 0; item < width; ++item)
            augmented[column * width + item] = static_cast<std::uint16_t>(augmented[column * width + item] * inverse % kPrime);
        for (std::uint64_t row = 0; row < count; ++row) {
            if (row == column) continue;
            const auto factor = augmented[row * width + column];
            if (factor == 0) continue;
            for (std::uint64_t item = 0; item < width; ++item) {
                const int updated = static_cast<int>(augmented[row * width + item]) - static_cast<int>(factor) * augmented[column * width + item];
                int reduced = updated % static_cast<int>(kPrime);
                if (reduced < 0) reduced += static_cast<int>(kPrime);
                augmented[row * width + item] = static_cast<std::uint16_t>(reduced);
            }
        }
    }
    std::vector<std::uint16_t> inverse(count * count);
    for (std::uint64_t row = 0; row < count; ++row)
        for (std::uint64_t column = 0; column < count; ++column)
            inverse[row * count + column] = augmented[row * width + count + column];
    return inverse;
}

void write_solution(const std::vector<std::uint8_t>& solution, const std::string& path) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot open solution output");
    output.write(reinterpret_cast<const char*>(solution.data()), static_cast<std::streamsize>(solution.size()));
    if (!output) throw std::runtime_error("failed writing solution output");
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const auto arguments = parse_arguments(argc, argv);
        const bool toy = arguments.toy;
        const std::uint64_t rows = toy ? 5 : kRows;
        const std::uint64_t columns = toy ? 3 : kColumns;
        const std::uint64_t rhs_count = toy ? 2 : kRhs;
        const Field field(kPrime);
        const auto total_started = Clock::now();

        const auto load_started = Clock::now();
        Matrix coefficient(field, rows, columns);
        SparseData data = toy ? load_toy(field, coefficient) : load_actual(field, arguments.csr_path, coefficient);
        std::vector<std::uint8_t> rhs = toy ? toy_rhs(data) : load_rhs(arguments.rhs_path, rows, rhs_count);
        const double load_seconds = seconds_since(load_started);

        const auto augmentation_started = Clock::now();
        Matrix augmented(field, rows, columns + rhs_count);
        Field::Element value;
        field.init(value);
        std::uint64_t rhs_nonzeros = 0;
        for (std::uint64_t row = 0; row < rows; ++row) {
            augmented[row] = coefficient[row];
            for (std::uint64_t column = 0; column < rhs_count; ++column) {
                const auto byte = rhs[row * rhs_count + column];
                if (byte) {
                    set_residue(field, value, byte);
                    augmented.setEntry(row, columns + column, value);
                    ++rhs_nonzeros;
                }
            }
        }
        const double augmentation_seconds = seconds_since(augmentation_started);

        LinBox::BlasMatrix<Field> nullspace(field, columns + rhs_count, rhs_count);
        LinBox::GaussDomain<Field> gauss(field);
        const auto solve_started = Clock::now();
        gauss.nullspacebasisin(nullspace, augmented);
        const double solve_seconds = seconds_since(solve_started);
        const auto nullity = nullspace.coldim();
        if (nullspace.rowdim() != columns + rhs_count)
            throw std::runtime_error("augmented nullspace row dimension drift");
        if (nullity != rhs_count) {
            std::cout << "{\"status\":\"STOP_CANONICAL_RESIDUAL_114_SECTION_NULLITY\""
                      << ",\"rows\":" << rows << ",\"columns\":" << columns
                      << ",\"rhs_count\":" << rhs_count << ",\"augmented_nullity\":" << nullity
                      << ",\"wall_seconds\":" << seconds_since(total_started) << "}" << std::endl;
            return 4;
        }

        const auto normalization_started = Clock::now();
        std::vector<std::uint16_t> bottom(rhs_count * rhs_count);
        for (std::uint64_t row = 0; row < rhs_count; ++row)
            for (std::uint64_t column = 0; column < rhs_count; ++column)
                bottom[row * rhs_count + column] = residue(field, nullspace.getEntry(columns + row, column));
        const auto bottom_inverse = invert_bottom(bottom, rhs_count);
        std::vector<std::uint8_t> solution(columns * rhs_count, 0);
        std::uint64_t solution_nonzeros = 0;
        for (std::uint64_t row = 0; row < columns; ++row) {
            std::vector<std::uint16_t> upper(rhs_count);
            for (std::uint64_t column = 0; column < rhs_count; ++column)
                upper[column] = residue(field, nullspace.getEntry(row, column));
            for (std::uint64_t column = 0; column < rhs_count; ++column) {
                std::uint64_t total = 0;
                for (std::uint64_t inner = 0; inner < rhs_count; ++inner)
                    total += upper[inner] * bottom_inverse[inner * rhs_count + column];
                const auto normalized = static_cast<std::uint8_t>((kPrime - total % kPrime) % kPrime);
                solution[row * rhs_count + column] = normalized;
                solution_nonzeros += normalized != 0;
            }
        }
        const double normalization_seconds = seconds_since(normalization_started);

        const auto replay_started = Clock::now();
        std::uint64_t replay_mismatches = 0;
        for (std::uint64_t row = 0; row < rows; ++row) {
            for (std::uint64_t rhs_column = 0; rhs_column < rhs_count; ++rhs_column) {
                std::uint64_t total = 0;
                for (std::uint64_t position = data.offsets[row]; position < data.offsets[row + 1]; ++position)
                    total += static_cast<std::uint64_t>(data.values[position]) * solution[data.columns[position] * rhs_count + rhs_column];
                replay_mismatches += static_cast<std::uint8_t>(total % kPrime) != rhs[row * rhs_count + rhs_column];
            }
        }
        std::uint64_t toy_known_mismatches = 0;
        if (toy) {
            const std::uint8_t known[3][2] = {{1, 2}, {3, 4}, {5, 6}};
            for (std::uint64_t row = 0; row < columns; ++row)
                for (std::uint64_t column = 0; column < rhs_count; ++column)
                    toy_known_mismatches += solution[row * rhs_count + column] != known[row][column];
        }
        const double replay_seconds = seconds_since(replay_started);
        write_solution(solution, arguments.solution_path);

        const bool passed = replay_mismatches == 0 && toy_known_mismatches == 0;
        std::cout << "{\"status\":\""
                  << (passed ? "PASS_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION" : "FAIL_LINBOX_P181_CANONICAL_RESIDUAL_114_SECTION")
                  << "\",\"mode\":\"" << (toy ? "toy_two_rhs" : "actual_114_rhs") << "\""
                  << ",\"rows\":" << rows << ",\"columns\":" << columns
                  << ",\"coefficient_nonzeros\":" << data.values.size()
                  << ",\"rhs_count\":" << rhs_count << ",\"rhs_nonzeros\":" << rhs_nonzeros
                  << ",\"augmented_nullity\":" << nullity
                  << ",\"solution_nonzeros\":" << solution_nonzeros
                  << ",\"replay_mismatches\":" << replay_mismatches
                  << ",\"toy_known_solution_mismatches\":" << toy_known_mismatches
                  << ",\"load_seconds\":" << load_seconds
                  << ",\"augmentation_seconds\":" << augmentation_seconds
                  << ",\"nullspace_seconds\":" << solve_seconds
                  << ",\"normalization_seconds\":" << normalization_seconds
                  << ",\"replay_seconds\":" << replay_seconds
                  << ",\"wall_seconds\":" << seconds_since(total_started) << "}" << std::endl;
        return passed ? 0 : 3;
    } catch (const std::exception& error) {
        std::cerr << "linbox_p181_canonical_residual_114_section_driver: " << error.what() << std::endl;
        return 2;
    }
}
