from zheka.api.dependencies.current_account import (
    CurrentAccount,
    CurrentAccountDep,
    RequireConsentDep,
)
from zheka.api.dependencies.current_org import (
    AdminOrgDep,
    CurrentOrg,
    CurrentOrgDep,
    LiveAdminOrgDep,
)
from zheka.api.dependencies.current_residency import (
    CurrentResidency,
    CurrentResidencyDep,
    ResidencyForFlatDep,
    ResidencyForFlatHouseDep,
    ResidencyForHouseDep,
)
from zheka.api.dependencies.current_user import CurrentUserDep
from zheka.api.dependencies.idempotency import IdempotencyDep

__all__ = (
    "AdminOrgDep",
    "CurrentAccount",
    "CurrentAccountDep",
    "CurrentOrg",
    "CurrentOrgDep",
    "CurrentResidency",
    "CurrentResidencyDep",
    "CurrentUserDep",
    "IdempotencyDep",
    "LiveAdminOrgDep",
    "RequireConsentDep",
    "ResidencyForFlatDep",
    "ResidencyForFlatHouseDep",
    "ResidencyForHouseDep",
)
