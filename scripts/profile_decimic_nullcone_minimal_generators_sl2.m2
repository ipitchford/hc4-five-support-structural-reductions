needsPackage "CoincidentRootLoci";
needsPackage "HighestWeights";

X = coincidentRootLocus {6, 1, 1, 1, 1};
R = ring X;
D = dynkinType{{"A", 1}};
variableWeights = toList apply(0..10, i -> {10 - 2*i});
setWeights(R, D, variableWeights);

I = trim ideal X;
generatorList = flatten entries gens I;
degree2 = select(generatorList, g -> first degree g == 2);
degree3 = select(generatorList, g -> first degree g == 3);
degree4 = select(generatorList, g -> first degree g == 4);

weights2 = apply(degree2, getWeights);
weights3 = apply(degree3, getWeights);
weights4 = apply(degree4, getWeights);
decomposition2 = decomposeWeightsList(D, weights2);
decomposition3 = decomposeWeightsList(D, weights3);
decomposition4 = decomposeWeightsList(D, weights4);

assert(decomposition2 == tally {{0}});
assert(decomposition3 == tally {{2}, {6}});
assert(decomposition4 == tally {{0}, {4}, {4}, {8}});

print("STATUS PASS_EXACT_SL2_MINIMAL_GENERATOR_DECOMPOSITION");
print("DEGREE_2_WEIGHTS " | toString tally weights2);
print("DEGREE_2_DECOMPOSITION " | toString decomposition2);
print("DEGREE_3_WEIGHTS " | toString tally weights3);
print("DEGREE_3_DECOMPOSITION " | toString decomposition3);
print("DEGREE_4_WEIGHTS " | toString tally weights4);
print("DEGREE_4_DECOMPOSITION " | toString decomposition4);

exit 0;
