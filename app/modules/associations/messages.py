"""Messages used by association management."""


class AssociationMessage:
    NOT_FOUND = "Association not found"
    FORBIDDEN = "Association access denied"
    SUBSCRIPTION_UPDATED = "Association subscription updated successfully"
    INVALID_WORKBOOK = "Invalid onboarding Excel file"
    WORKBOOK_SHEETS_REQUIRED = "Excel file must contain Association Details, Unit Details, and Homeowner Details sheets"
    ASSOCIATION_SHEET_EMPTY = "Association details sheet is empty"
    INVALID_UNIT_REFERENCE = "A homeowner references a unit that does not exist in the Unit Details sheet"
    PRIMARY_HOMEOWNER_COLUMN_REQUIRED = "Homeowner Details must include a Primary Homeowner column"
    PRIMARY_HOMEOWNER_INVALID = "Primary Homeowner must be Yes or No for every homeowner"
    PRIMARY_HOMEOWNER_PER_UNIT_REQUIRED = "Each unit or home must have exactly one primary homeowner"
    PRIMARY_HOMEOWNER_EMAIL_REQUIRED = "Each primary homeowner must have an email address"
    FLOORS_NOT_ALLOWED = "Townhouse and Single Family workbooks must leave the Floor column blank"
    ENTITY_NOT_FOUND = "Organization entity not found"
    PLAN_NOT_FOUND = "Subscription plan not found"
