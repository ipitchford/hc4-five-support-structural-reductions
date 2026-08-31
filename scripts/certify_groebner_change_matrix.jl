#!/usr/bin/env julia

using Groebner
using JSON3
using Nemo
using SHA


function argument_value(name::String)
    index = findfirst(==(name), ARGS)
    index === nothing && error("missing argument $(name)")
    index == length(ARGS) && error("missing value after $(name)")
    ARGS[index + 1]
end


function rational_coefficient(term)
    numerator_value = parse(BigInt, String(term["numerator"]))
    denominator_value = parse(BigInt, String(term["denominator"]))
    QQ(numerator_value, denominator_value)
end


function sparse_polynomial(terms, ring, variables)
    result = zero(ring)
    for term in terms
        monomial = one(ring)
        for (variable, exponent) in zip(variables, term["exponents"])
            monomial *= variable^Int(exponent)
        end
        result += rational_coefficient(term) * monomial
    end
    result
end


function sparse_terms(polynomial)
    result = Vector{Dict{String, Any}}()
    for (coefficient, exponents) in zip(coefficients(polynomial), exponent_vectors(polynomial))
        push!(
            result,
            Dict(
                "numerator" => string(numerator(coefficient)),
                "denominator" => string(denominator(coefficient)),
                "exponents" => collect(exponents),
            ),
        )
    end
    result
end


input_path = abspath(argument_value("--input"))
output_path = abspath(argument_value("--output"))
input = JSON3.read(read(input_path, String))
variable_names = String.(input["variable_names"])
ring, variables = polynomial_ring(QQ, variable_names)
generators = [sparse_polynomial(terms, ring, variables) for terms in input["equations"]]

timing = @timed begin
    basis, change_matrix = groebner_with_change_matrix(
        generators;
        ordering=DegRevLex(),
        certify=true,
    )
    (basis, change_matrix)
end
basis, change_matrix = timing.value
matrix_replay = change_matrix * generators
matrix_replay == basis || error("Groebner change matrix does not replay the returned basis")

unit_index = findfirst(
    polynomial -> !iszero(polynomial) && total_degree(polynomial) == 0,
    basis,
)
unit_index === nothing && error("the certified basis does not contain a nonzero constant")
unit_constant = first(coefficients(basis[unit_index]))
unit_multipliers = [change_matrix[unit_index, column] / unit_constant for column in axes(change_matrix, 2)]
reconstructed_unit = sum(
    multiplier * generator for (multiplier, generator) in zip(unit_multipliers, generators);
    init=zero(ring),
)
isone(reconstructed_unit) || error("normalized change-matrix row does not reconstruct 1")

project_path = normpath(joinpath(@__DIR__, "..", "tools", "groebner-jl", "Project.toml"))
manifest_path = normpath(joinpath(@__DIR__, "..", "tools", "groebner-jl", "Manifest.toml"))
certificate = Dict(
    "schema" => "exact-groebner-unit-change-matrix-v1",
    "status" => "PASS_EXACT_UNIT_CHANGE_MATRIX",
    "field" => "QQ",
    "ordering" => "DegRevLex",
    "certify" => true,
    "input_path" => input_path,
    "input_sha256" => bytes2hex(sha256(read(input_path))),
    "input_schema" => String(input["schema"]),
    "chart" => String(input["chart"]),
    "branch" => String(input["branch"]),
    "variable_names" => variable_names,
    "generator_count" => length(generators),
    "basis_size" => length(basis),
    "unit_basis_index" => unit_index,
    "unit_basis_constant" => string(unit_constant),
    "matrix_replay_exact" => true,
    "unit_reconstruction_exact" => true,
    "unit_multiplier_terms" => [sparse_terms(multiplier) for multiplier in unit_multipliers],
    "wall_seconds" => timing.time,
    "allocated_bytes" => timing.bytes,
    "gc_seconds" => timing.gctime,
    "julia_version" => string(VERSION),
    "groebner_version" => string(Base.pkgversion(Groebner)),
    "nemo_version" => string(Base.pkgversion(Nemo)),
    "json3_version" => string(Base.pkgversion(JSON3)),
    "project_sha256" => bytes2hex(sha256(read(project_path))),
    "manifest_sha256" => bytes2hex(sha256(read(manifest_path))),
    "claim_boundary" => "This certificate proves the unit ideal for exactly one exported characteristic-zero branch; the full chart requires a certified cover of every branch.",
)

mkpath(dirname(output_path))
open(output_path, "w") do io
    JSON3.write(io, certificate)
    write(io, '\n')
end
println(
    JSON3.write(
        Dict(
            "output" => output_path,
            "status" => certificate["status"],
            "chart" => certificate["chart"],
            "branch" => certificate["branch"],
            "generator_count" => certificate["generator_count"],
            "basis_size" => certificate["basis_size"],
            "wall_seconds" => certificate["wall_seconds"],
            "allocated_bytes" => certificate["allocated_bytes"],
        ),
    ),
)
