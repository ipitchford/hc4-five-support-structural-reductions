needsPackage "CoincidentRootLoci";
needsPackage "HighestWeights";

X = coincidentRootLocus {6, 1, 1, 1, 1};
R = ring X;
D = dynkinType{{"A", 1}};
variableWeights = toList apply(0..10, i -> {10 - 2*i});
setWeights(R, D, variableWeights);

I = trim ideal X;
generatorList = flatten entries gens I;

v0QuadraticCandidates = select(generatorList, g -> first degree g == 2 and getWeights g == {0});
v6Candidates = select(generatorList, g -> first degree g == 3 and getWeights g == {6});
v2WeightCandidates = select(generatorList, g -> first degree g == 3 and getWeights g == {2});
v8Candidates = select(generatorList, g -> first degree g == 4 and getWeights g == {8});
v4WeightCandidates = select(generatorList, g -> first degree g == 4 and getWeights g == {4});
v0WeightCandidates = select(generatorList, g -> first degree g == 4 and getWeights g == {0});

assert(#v0QuadraticCandidates == 1);
assert(#v6Candidates == 1);
assert(#v2WeightCandidates == 2);
assert(#v8Candidates == 1);
assert(#v4WeightCandidates == 3);
assert(#v0WeightCandidates == 4);

print("STATUS PASS_EXACT_WEIGHT_SPACE_EXTRACTION");
print("V0_QUADRATIC_BEGIN");
print(toExternalString first v0QuadraticCandidates);
print("V0_QUADRATIC_END");
print("V6_CUBIC_BEGIN");
print(toExternalString first v6Candidates);
print("V6_CUBIC_END");
print("V2_WEIGHT_2_CANDIDATES_BEGIN");
scan(v2WeightCandidates, g -> print toExternalString g);
print("V2_WEIGHT_2_CANDIDATES_END");
print("V8_QUARTIC_BEGIN");
print(toExternalString first v8Candidates);
print("V8_QUARTIC_END");
print("V4_WEIGHT_4_CANDIDATES_BEGIN");
scan(v4WeightCandidates, g -> print toExternalString g);
print("V4_WEIGHT_4_CANDIDATES_END");
print("V0_WEIGHT_0_CANDIDATES_BEGIN");
scan(v0WeightCandidates, g -> print toExternalString g);
print("V0_WEIGHT_0_CANDIDATES_END");

exit 0;
