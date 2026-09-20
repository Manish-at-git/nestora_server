"""Messages used by feature catalogue management."""


class FeatureMessage:
    NAME_EXISTS = "Feature name already exists"
    CODE_EXISTS = "Feature code already exists"
    NOT_FOUND = "Feature not found"
    PARENT_NOT_FOUND = "Parent feature not found"
    PARENT_CYCLE = "A feature cannot be its own parent or descendant"
