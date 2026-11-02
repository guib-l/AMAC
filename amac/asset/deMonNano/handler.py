from amac.engine.handler import handler

__all__ = [
    "properties",
    "ground_energy",
    "energy_resume",
    "final_geometry",
    "gradient",
]


@handler(software="deMonNano", name="properties")
def properties(results):

    return results["properties"]

@handler(software="deMonNano", name="ground_energy")
def ground_energy(results):

    return results["energy"]["energy"]

@handler(software="deMonNano", name="energy_resume")
def energy_resume(results):

    return results["energy"]

@handler(
    software="deMonNano",
    name="gradient",
    modules=("optimization-geometry",),
)
def gradient(results):

    return results["forces"]

@handler(software="deMonNano", name="final_geometry")
def final_geometry(results):

    return results["output_geometry"]
