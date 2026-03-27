# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_do_itbis_amount = fields.Monetary(
        string="Monto ITBIS (DGII)",
        compute="_compute_l10n_do_itbis_amount",
        store=True,
        currency_field="currency_id",
        help="Cálculo aislado del ITBIS por línea para el XML de Facturación Electrónica."
    )

    @api.depends('tax_ids', 'price_subtotal', 'quantity', 'price_unit', 'discount')
    def _compute_l10n_do_itbis_amount(self):
        """
        Calcula el monto específico de ITBIS en esta línea, ignorando otros impuestos 
        como el ISC o Retenciones, ya que el e-CF exige separar el ITBIS (TipoImpuesto = 1).
        """
        for line in self:
            itbis_amount = 0.0
            if line.move_id.country_code == 'DO' and line.tax_ids:
                # Filtramos solo los impuestos que pertenezcan al grupo ITBIS
                itbis_taxes = line.tax_ids.filtered(
                    lambda t: 'ITBIS' in (t.tax_group_id.name or '').upper())

                if itbis_taxes:
                    # Calculamos el impuesto sobre el precio con descuento
                    price_with_discount = line.price_unit * \
                        (1 - (line.discount or 0.0) / 100.0)
                    taxes_res = itbis_taxes.compute_all(
                        price_with_discount,
                        currency=line.currency_id,
                        quantity=line.quantity,
                        product=line.product_id,
                        partner=line.move_id.partner_id,
                        is_refund=line.move_id.move_type in (
                            'out_refund', 'in_refund'),
                    )
                    itbis_amount = sum(t.get('amount', 0.0)
                                       for t in taxes_res.get('taxes', []))

            line.l10n_do_itbis_amount = abs(itbis_amount)
