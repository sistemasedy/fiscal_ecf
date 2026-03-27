# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Configuraciones Generales DGII ---
    l10n_do_dgii_start_date = fields.Date(
        related='company_id.l10n_do_dgii_start_date',
        readonly=False,
    )
    l10n_do_default_client = fields.Selection(
        related='company_id.l10n_do_default_client',
        readonly=False,
    )
    l10n_do_ecf_issuer = fields.Boolean(
        related='company_id.l10n_do_ecf_issuer',
        readonly=False,
    )
    l10n_do_ecf_deferred_submissions = fields.Boolean(
        related='company_id.l10n_do_ecf_deferred_submissions',
        readonly=False,
    )

    # --- Credenciales e-CF ---
    l10n_do_ecf_env = fields.Selection(
        related='company_id.l10n_do_ecf_env',
        readonly=False
    )
    l10n_do_ecf_certificate = fields.Binary(
        related='company_id.l10n_do_ecf_certificate',
        readonly=False
    )
    l10n_do_ecf_cert_password = fields.Char(
        related='company_id.l10n_do_ecf_cert_password',
        readonly=False
    )
    l10n_do_ecf_cert_is_valid = fields.Boolean(
        related='company_id.l10n_do_ecf_cert_is_valid',
        readonly=True  # Es readonly porque es un campo calculado automáticamente
    )
