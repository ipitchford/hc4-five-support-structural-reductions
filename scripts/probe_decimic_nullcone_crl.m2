needsPackage "CoincidentRootLoci";

X = coincidentRootLocus {6, 1, 1, 1, 1};
I = trim ideal X;
generatorDegrees = flatten apply(degrees source gens I, d -> d#0);

assert(dim X == 5);
assert(codim X == 5);
assert(degree X == 30);
assert(numgens I == 31);
assert(tally generatorDegrees == tally {2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
                                        4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
                                        4, 4, 4, 4, 4, 4, 4, 4, 4, 4});

print("STATUS PASS_EXACT_NULLCONE_IDEAL_PROFILE");
print("PARTITION 6,1,1,1,1");
print("PROJECTIVE_DIMENSION " | toString dim X);
print("CODIMENSION " | toString codim X);
print("DEGREE " | toString degree X);
print("GENERATOR_COUNT " | toString numgens I);
print("GENERATOR_DEGREES " | toString generatorDegrees);

exit 0;
