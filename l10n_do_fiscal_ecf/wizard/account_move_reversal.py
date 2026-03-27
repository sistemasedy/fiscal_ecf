# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_do_ecf_modification_code = fields.Selection(
        selection=lambda self: self.env["account.move"]._fields['l10n_do_ecf_modification_code'].selection,
        string="Código de Modificación e-CF",
        help="Requerido por la DGII para Notas de Crédito Electrónicas."
    )

    def reverse_moves(self):
        # Ejecutamos la lógica nativa de Odoo para crear la nota de crédito
        res = super(AccountMoveReversal, self).reverse_moves()

        # Si se creó correctamente y estamos en RD, inyectamos los datos fiscales
        if 'res_id' in res and self.env.company.country_code == 'DO':
            refund_move = self.env['account.move'].browse(res['res_id'])
            original_move = self.move_ids[0] if self.move_ids else False

            if original_move:
                refund_move.write({
                    'l10n_do_ecf_modification_code': self.l10n_do_ecf_modification_code or '1',
                    'l10n_do_origin_ncf': original_move.name,
                })

        return res
