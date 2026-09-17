from zheka.api.dependencies.current_account import (
    CurrentAccount,
    CurrentAccountDep,
    RequireConsentDep,
)
from zheka.api.dependencies.current_org import (
    AdminOrgDep,
    CurrentOrg,
    CurrentOrgDep,
)
from zheka.api.dependencies.current_residency import (
    CurrentResidency,
    CurrentResidencyDep,
    ResidencyForFlatDep,
    ResidencyForFlatHouseDep,
    ResidencyForHouseDep,
)
from zheka.api.dependencies.current_user import CurrentUser, CurrentUserDep

__all__ = (
    "AdminOrgDep",
    "CurrentAccount",
    "CurrentAccountDep",
    "CurrentOrg",
    "CurrentOrgDep",
    "CurrentResidency",
    "CurrentResidencyDep",
    "CurrentUser",
    "CurrentUserDep",
    "RequireConsentDep",
    "ResidencyForFlatDep",
    "ResidencyForFlatHouseDep",
    "ResidencyForHouseDep",
)
