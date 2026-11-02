from amac.engine.handler import handler

__all__ = [
    "properties",
    "ground_energy",
    "energy_resume",
    "final_geometry",
    "gradient",
]


@handler(software="dftb+", name="properties")
def properties(results):

    return results["properties"]

@handler(software="dftb+", name="ground_energy")
def ground_energy(results):

    return results["energy"]["energy"]

@handler(software="dftb+", name="energy_resume")
def energy_resume(results):

    return results["energy"]

@handler(
    software="dftb+",
    name="gradient",
    modules=("optimization-geometry",),
)
def gradient(results):

    return results["forces"]

@handler(software="dftb+", name="final_geometry")
def final_geometry(results):

    return results["output_geometry"]
