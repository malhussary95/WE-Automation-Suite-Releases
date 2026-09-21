FIELD_OPTIONS = [
    "Order",
    "CST Name",
    "CST Name Arabic",
    "CST Number",
    "CST Type",
    "CST Category",
    "Branch",
    "Branch Address",
    "Account manager",
    "Account manager mail",
    "Order Status",
    "SO Type",
    "SO Status",
    "Latest SO",
    "Current Task",
    "Latest Migration by E-Support SO",
    "Migration SO Type",
    "Migration SO Status",
    "Migration Current Task",
    "Migration Current Task Owner",
    "CID",
    "Circuit Status",
    "Request Number",
    "ESPT & infra status",
    "Notes",
    "NID",
    "Speed",
    "Hardware",
    "Product",
    "Transmission Type",
    "Network Data",
    "MSAN Data",
    "POP",
    "Work Order PDF",
    "Installed Resources",
    "ONU Tech Data",

]

FIELD_PRESETS = {
    "Technical Check": ["Order", "CID", "Speed", "Network Data", "MSAN Data", "POP", "NID"],
    "Migration Audit": [
        "Order", "Latest SO", "SO Status", "Latest Migration by E-Support SO",
        "Migration SO Type", "Migration SO Status", "Migration Current Task",
        "Migration Current Task Owner", "ESPT & infra status", "Current Task",
        "Notes", "Request Number", "CID"
    ],
    "Customer Profile": ["CST Name", "CST Name Arabic", "CST Number", "Branch", "Account manager"],
    "Full Report": FIELD_OPTIONS
}

SO_REQUIRED_FIELDS = {

    "CST Name",
    "Branch",
    "Speed",
    "Latest SO",
    "Latest Migration by E-Support SO",
    "Migration SO Type",
    "Migration SO Status",
    "Migration Current Task",
    "SO Status",
    "SO Type",
    "Current Task",
    "POP",

    # =====================================================
    # REQUIRED FOR SO COMPONENTS
    # =====================================================
    "CID",
    "Request Number",
    "ESPT & infra status",

    "CST Name Arabic",
    "CST Type",
    "CST Category",
    "Account manager",
    "Account manager mail",
    "Branch Address",
    "CST Number",
    "Notes",
    "ONU Tech Data",
}

RESOURCE_REQUIRED_FIELDS = {
    "Network Data",
    "NID",
    "MSAN Data",
    "POP",
    "Work Order PDF",
    "ONU Tech Data",
    "Circuit Status",
    "Request Number",
}

IB_REQUIRED_FIELDS = {
    "Speed",
    "Order Status",
    "Hardware",
    "Product",
    "Transmission Type",
    "CST Name",
    "CST Name Arabic",
    "CST Number",
    "CST Type",
    "CST Category",
    "Branch",
    "Branch Address",
    "Account manager",
    "Account manager mail",
    "Work Order PDF",
    "ONU Tech Data",
}

RESULT_REQUIRED_FIELDS = {

    "CID",
    "Request Number",
    "ESPT & infra status",
    "ONU Tech Data",
    "Work Order PDF",
}

CUSTOMER_JSON_REQUIRED_FIELDS = {
    "CST Name Arabic",
    "CST Type",
    "CST Category",
    "Account manager",
    "Account manager mail",
}

USER_JSON_REQUIRED_FIELDS = {
    "Account manager mail",
}

BRANCH_JSON_REQUIRED_FIELDS = {
    "Branch Address",
    "CST Number",
}
