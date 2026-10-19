"""Form 8-K item codes and their official names (SEC Form 8-K General Instructions)."""

ITEM_NAMES = {
    "1.01": "Entry into a Material Definitive Agreement",
    "1.02": "Termination of a Material Definitive Agreement",
    "1.03": "Bankruptcy or Receivership",
    "1.04": "Mine Safety - Reporting of Shutdowns and Patterns of Violations",
    "1.05": "Material Cybersecurity Incidents",
    "2.01": "Completion of Acquisition or Disposition of Assets",
    "2.02": "Results of Operations and Financial Condition",
    "2.03": (
        "Creation of a Direct Financial Obligation or an Obligation under an "
        "Off-Balance Sheet Arrangement of a Registrant"
    ),
    "2.04": (
        "Triggering Events That Accelerate or Increase a Direct Financial Obligation or an "
        "Obligation under an Off-Balance Sheet Arrangement"
    ),
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": (
        "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard; "
        "Transfer of Listing"
    ),
    "3.02": "Unregistered Sales of Equity Securities",
    "3.03": "Material Modification to Rights of Security Holders",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": (
        "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report "
        "or Completed Interim Review"
    ),
    "5.01": "Changes in Control of Registrant",
    "5.02": (
        "Departure of Directors or Certain Officers; Election of Directors; Appointment of "
        "Certain Officers; Compensatory Arrangements of Certain Officers"
    ),
    "5.03": "Amendments to Articles of Incorporation or Bylaws; Change in Fiscal Year",
    "5.04": "Temporary Suspension of Trading Under Registrant's Employee Benefit Plans",
    "5.05": (
        "Amendment to Registrant's Code of Ethics, or Waiver of a Provision of the Code of Ethics"
    ),
    "5.06": "Change in Shell Company Status",
    "5.07": "Submission of Matters to a Vote of Security Holders",
    "5.08": "Shareholder Director Nominations",
    "6.01": "ABS Informational and Computational Material",
    "6.02": "Change of Servicer or Trustee",
    "6.03": "Change in Credit Enhancement or Other External Support",
    "6.04": "Failure to Make a Required Distribution",
    "6.05": "Securities Act Updating Disclosure",
    "7.01": "Regulation FD Disclosure",
    "8.01": "Other Events",
    "9.01": "Financial Statements and Exhibits",
}

# Items that make an 8-K a labelled event for Gold-Event (material / risk-relevant events)
EVENT_ITEMS = (
    "1.01", "1.03", "1.05", "2.01", "2.04", "2.05", "2.06", "3.01", "4.01", "4.02", "5.02", "8.01",
)  # fmt: skip

# Plain-English descriptions of risk events, for questions
EVENT_PHRASES = {
    "1.03": "a Chapter 11 bankruptcy filing",
    "1.05": "a material cybersecurity incident",
    "2.04": "a triggering event that accelerated a debt obligation",
    "2.06": "a material impairment charge",
    "4.01": "a change in its independent auditor",
    "4.02": "that previously issued financial statements should no longer be relied upon",
}
