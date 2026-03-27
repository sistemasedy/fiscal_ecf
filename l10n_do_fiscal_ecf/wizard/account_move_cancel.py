# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError


class AccountMoveCancel(models.TransientModel):
    _name = "account.move.cancel"
    _description = "Asistente de Cancelación de Facturas (DGII)"

    # Heredamos las opciones del modelo account.move
    l10n_do_cancellation_type = fields.Selection(
        selection=lambda self: self.env["account.move"]._fields['l10n_do_cancellation_type'].selection,
        string="Tipo de Anulación (DGII)",
        required=True,
    )

    def move_cancel(self):
        active_ids = self._context.get("active_ids", [])
        moves = self.env["account.move"].browse(active_ids)

        for invoice in moves:
            if invoice.state == "cancel":
                raise UserError(_("Esta factura ya se encuentra cancelada."))

            if invoice.payment_state not in ("not_paid", "reversed"):
                raise UserError(
                    _("No puede anular una factura que ya tiene pagos registrados. Debe desconciliar los pagos primero."))

            # Escribimos el motivo de anulación en la factura
            invoice.write({
                "l10n_do_cancellation_type": self.l10n_do_cancellation_type,
            })

            # Forzamos la cancelación (inyectando una variable de contexto para evitar un bucle
            # con el botón que interceptamos en account.move)
            invoice.with_context(force_cancel=True).button_cancel()

        return {"type": "ir.actions.act_window_close"}
