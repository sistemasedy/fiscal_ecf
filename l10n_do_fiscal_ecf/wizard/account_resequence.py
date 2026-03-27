# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError


class ReSequenceWizard(models.TransientModel):
    _inherit = "account.resequence.wizard"

    @api.model
    def default_get(self, fields_list):
        ctx = self.env.context

        if "active_model" in ctx and ctx["active_model"] == "account.move" and "active_ids" in ctx:
            moves = self.env["account.move"].browse(ctx["active_ids"])

            # Filtramos si hay alguna factura de República Dominicana con NCF
            do_moves = moves.filtered(
                lambda m: m.country_code == 'DO' and m.l10n_latam_use_documents)

            if do_moves:
                raise UserError(_(
                    "Operación Bloqueada por Normativa DGII:\n"
                    "No está permitido re-secuenciar Comprobantes Fiscales (NCF/e-CF). "
                    "Si cometió un error, debe anular el comprobante (Formato 608) y emitir uno nuevo."
                ))

        return super(ReSequenceWizard, self).default_get(fields_list)
