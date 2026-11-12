# Importing the assets registers them in Software.
from amac.asset.deMonNano.soft import software_deMonNano  # noqa: F401
from amac.asset.dftbplus.soft import software_dftbplus  # noqa: F401
from amac.asset.orca.soft import software_orca  # noqa: F401
from amac.asset.pyscf.soft import software_pyscf  # noqa: F401
from amac.engine.software import Software

resolved_software = Software.create
