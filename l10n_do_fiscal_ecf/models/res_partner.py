# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import AccessError


class Partner(models.Model):
    _inherit = "res.partner"

    def _get_l10n_do_dgii_payer_types_selection(self):
        return [
            ("taxpayer", _("Crédito Fiscal (Taxpayer)")),
            ("non_payer", _("Consumidor Final (Non Payer)")),
            ("nonprofit", _("Institución sin Fines de Lucro")),
            ("special", _("Régimen Especial")),
            ("governmental", _("Gubernamental")),
            ("foreigner", _("Extranjero")),
        ]

    def _get_l10n_do_expense_type(self):
        return [
            ("01", _("01 - Gastos de Personal")),
            ("02", _("02 - Gastos por Trabajos, Suministros y Servicios")),
            ("03", _("03 - Arrendamientos")),
            ("04", _("04 - Gastos de Activos Fijos")),
            ("05", _("05 - Gastos de Representación")),
            ("06", _("06 - Otras Deducciones Admitidas")),
            ("07", _("07 - Gastos Financieros")),
            ("08", _("08 - Gastos Extraordinarios")),
            ("09", _("09 - Compras y Gastos que forman parte del Costo de Ventas")),
            ("10", _("10 - Adquisiciones de Activos")),
            ("11", _("11 - Gastos de Seguros")),
        ]

    l10n_do_dgii_tax_payer_type = fields.Selection(
        selection="_get_l10n_do_dgii_payer_types_selection",
        compute="_compute_l10n_do_dgii_payer_type",
        inverse="_inverse_l10n_do_dgii_tax_payer_type",
        string="Tipo de Contribuyente",
        index=True,
        store=True,
    )

    l10n_do_expense_type = fields.Selection(
        selection="_get_l10n_do_expense_type",
        string="Tipo de Costo y Gasto",
        store=True,
        help="Requerido para el reporte 606",
    )

    def _check_l10n_do_fiscal_fields(self, vals):
        if not self or self.parent_id:
            return

        fiscal_fields = [f for f in ["name", "vat", "country_id"] if f in vals]
        if fiscal_fields:
            # Si el contacto ya tiene facturas publicadas, bloqueamos el cambio
            has_invoices = self.env["account.move"].sudo().search([
                ("l10n_latam_use_documents", "=", True),
                ("country_code", "=", "DO"),
                ("commercial_partner_id", "=", self.id),
                ("state", "=", "posted"),
            ], limit=1)

            if has_invoices and not self.env.user.has_group('base.group_system'):
                raise AccessError(
                    _("No puedes modificar %s porque este contacto ya tiene facturas fiscales emitidas.")
                    % (", ".join(self._fields[f].string for f in fiscal_fields))
                )

    def write(self, vals):
        res = super(Partner, self).write(vals)
        self._check_l10n_do_fiscal_fields(vals)
        return res

    @api.depends("vat", "country_id", "name")
    def _compute_l10n_do_dgii_payer_type(self):
        for partner in self:
            vat = str(partner.vat if partner.vat else partner.name or '')
            is_do = partner.country_id.code == 'DO' if partner.country_id else True

            if partner.country_id and not is_do:
                partner.l10n_do_dgii_tax_payer_type = "foreigner"
                continue

            if vat and (not partner.l10n_do_dgii_tax_payer_type or partner.l10n_do_dgii_tax_payer_type == "non_payer"):
                clean_vat = ''.join(filter(str.isdigit, vat))

                if len(clean_vat) == 9:
                    if partner.name and "MINISTERIO" in partner.name.upper():
                        partner.l10n_do_dgii_tax_payer_type = "governmental"
                    elif partner.name and any(n in partner.name.upper() for n in ("IGLESIA", "ZONA FRANCA")):
                        partner.l10n_do_dgii_tax_payer_type = "special"
                    elif clean_vat.startswith("4"):
                        partner.l10n_do_dgii_tax_payer_type = "nonprofit"
                    else:
                        partner.l10n_do_dgii_tax_payer_type = "taxpayer"

                elif len(clean_vat) == 11:
                    default_client = self.env.company.l10n_do_default_client
                    partner.l10n_do_dgii_tax_payer_type = default_client if default_client else "non_payer"
                else:
                    partner.l10n_do_dgii_tax_payer_type = "non_payer"

            elif not partner.l10n_do_dgii_tax_payer_type:
                partner.l10n_do_dgii_tax_payer_type = "non_payer"

    def _inverse_l10n_do_dgii_tax_payer_type(self):
        for partner in self:
            partner.l10n_do_dgii_tax_payer_type = partner.l10n_do_dgii_tax_payer_type
