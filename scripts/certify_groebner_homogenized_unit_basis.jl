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


function optional_argument_value(name::String, default::String)
    index = findfirst(==(name), ARGS)
    index === nothing && return default
    index == length(ARGS) && error("missing value after $(name)")
    ARGS[index + 1]
end


function sparse_polynomial(terms, ring, variables)
    result = zero(ring)
    for term in terms
        coefficient = QQ(
            parse(BigInt, String(term["numerator"])),
            parse(BigInt, String(term["denominator"])),
        )
        monomial = one(ring)
        for (variable, exponent) in zip(variables, term["exponents"])
            monomial *= variable^Int(exponent)
        end
        result += coefficient * monomial
    end
    result
end


input_path = abspath(argument_value("--input"))
output_path = abspath(argument_value("--output"))
modular_name = optional_argument_value("--modular", "auto")
modular_name in ("auto", "classic_modular", "learn_and_apply") ||
    error("--modular must be auto, classic_modular, or learn_and_apply")
modular_backend = Symbol(modular_name)
input = JSON3.read(read(input_path, String))
variable_names = String.(input["variable_names"])
ring, variables = polynomial_ring(QQ, variable_names)
generators = [sparse_polynomial(terms, ring, variables) for terms in input["equations"]]

timing = @timed begin
    groebner(
        generators;
        ordering=DegRevLex(),
        reduced=true,
        certify=true,
        homogenize=:yes,
        linalg=:deterministic,
        modular=modular_backend,
        tasks=1,
    )
end
basis = timing.value
unit_basis = length(basis) == 1 && isone(basis[1])
unit_basis || error("the certified homogenized computation did not return the unit basis")

project_path = normpath(joinpath(@__DIR__, "..", "tools", "groebner-jl", "Project.toml"))
manifest_path = normpath(joinpath(@__DIR__, "..", "tools", "groebner-jl", "Manifest.toml"))
receipt = Dict(
    "schema" => "exact-homogenized-groebner-unit-basis-v1",
    "status" => "PASS_EXACT_HOMOGENIZED_CERTIFIED_UNIT_BASIS",
    "field" => "QQ",
    "ordering" => "DegRevLex",
    "reduced" => true,
    "certify" => true,
    "homogenize" => "yes",
    "linear_algebra" => "deterministic",
    "modular_backend" => modular_name,
    "tasks" => 1,
    "input_path" => input_path,
    "input_sha256" => bytes2hex(sha256(read(input_path))),
    "input_schema" => String(input["schema"]),
    "chart" => String(input["chart"]),
    "branch" => String(input["branch"]),
    "variable_names" => variable_names,
    "generator_count" => length(generators),
    "retained_generator_indices" => collect(input["retained_generator_indices"]),
    "basis_size" => length(basis),
    "basis" => string.(basis),
    "unit_basis_exact" => unit_basis,
    "wall_seconds" => timing.time,
    "allocated_bytes" => timing.bytes,
    "gc_seconds" => timing.gctime,
    "julia_version" => string(VERSION),
    "groebner_version" => string(Base.pkgversion(Groebner)),
    "nemo_version" => string(Base.pkgversion(Nemo)),
    "json3_version" => string(Base.pkgversion(JSON3)),
    "project_sha256" => bytes2hex(sha256(read(project_path))),
    "manifest_sha256" => bytes2hex(sha256(read(manifest_path))),
    "claim_boundary" => "This is an exact deterministic homogenized characteristic-zero Groebner computation for one exported branch.  It does not provide an explicit Bezout multiplier row and does not cover other branches.",
)
mkpath(dirname(output_path))
open(output_path, "w") do io
    JSON3.write(io, receipt)
    write(io, '\n')
end
println(
    JSON3.write(
        Dict(
            "output" => output_path,
            "status" => receipt["status"],
            "chart" => receipt["chart"],
            "branch" => receipt["branch"],
            "generator_count" => receipt["generator_count"],
            "basis" => receipt["basis"],
            "wall_seconds" => receipt["wall_seconds"],
            "allocated_bytes" => receipt["allocated_bytes"],
        ),
    ),
)
