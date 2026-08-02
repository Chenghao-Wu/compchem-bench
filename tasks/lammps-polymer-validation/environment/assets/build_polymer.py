import math

N_CHAINS = 10
N_BEADS = 20
N = N_CHAINS * N_BEADS

density = 0.85
L = (N / density) ** (1/3)

spacing = L / 6

# 6x6x6 lattice
sites = []

for z in range(6):
    for y in range(6):
        for x in range(6):
            sites.append(
                (
                    (x+0.5)*spacing,
                    (y+0.5)*spacing,
                    (z+0.5)*spacing
                )
            )

# use first 200 lattice points
beads = sites[:N]

chains=[]
for i in range(N_CHAINS):
    chains.append(
        beads[i*N_BEADS:(i+1)*N_BEADS]
    )


with open("polymer.data","w") as f:

    f.write("Kremer-Grest polymer melt\n\n")

    f.write(f"{N} atoms\n")
    f.write(f"{N_CHAINS*(N_BEADS-1)} bonds\n\n")

    f.write("1 atom types\n")
    f.write("1 bond types\n\n")

    f.write(f"0 {L} xlo xhi\n")
    f.write(f"0 {L} ylo yhi\n")
    f.write(f"0 {L} zlo zhi\n\n")

    f.write("Masses\n\n")
    f.write("1 1.0\n\n")

    f.write("Atoms # molecular\n\n")

    aid=1

    for mol,chain in enumerate(chains,1):

        for x,y,z in chain:

            f.write(
                f"{aid} {mol} 1 {x} {y} {z}\n"
            )

            aid+=1


    f.write("\nBonds\n\n")

    bid=1

    for mol in range(N_CHAINS):

        start=mol*N_BEADS+1

        for i in range(N_BEADS-1):

            f.write(
                f"{bid} 1 {start+i} {start+i+1}\n"
            )

            bid+=1


print("polymer generated")