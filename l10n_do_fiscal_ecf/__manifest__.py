# -*- coding: utf-8 -*-
{
    "name": "Fiscal Accounting & e-CF (Rep. Dominicana)",
    "summary": """
        Localización Fiscal, Gestión de NCF y Facturación Electrónica (e-CF) 
        para la República Dominicana (Odoo 18).
    """,
    "author": "CONSTRUCCIONES LAMOUT S.R.L. / Edy",
    "category": "Accounting/Localizations",
    "license": "LGPL-3",
    "version": "18.0.1.0.0",
    "depends": [
        "account",
        "l10n_latam_invoice_document",
        "l10n_do",
    ],
    "external_dependencies": {
        "python": ["signxml", "cryptography", "lxml", "requests"],
    },
    "data": [
        # 1. Seguridad
        "security/res_groups.xml",
        "security/ir.model.access.csv",

        # 2. Datos y Cron Jobs
        "data/ir_cron.xml",

        # 3. Vistas de Wizards
        "wizard/wizard_views.xml",

        # 4. Vistas de Modelos
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",

        # 5. Reportes (PDF)
        "views/report_invoice.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
