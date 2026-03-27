# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    l10n_do_ecf_modification_code = fields.Selection(
        selection=lambda self: self.env["account.move"]._fields['l10n_do_ecf_modification_code'].selection,
        string="Código de Modificación e-CF",
        help="Requerido por la DGII para Notas de Débito Electrónicas."
    )

    def create_debit(self):
        # Ejecutamos la lógica nativa de Odoo
        res = super(AccountDebitNote, self).create_debit()

        # Inyectamos el NCF modificado a la nueva Nota de Débito
        if 'res_id' in res and self.env.company.country_code == 'DO':
            debit_move = self.env['account.move'].browse(res['res_id'])
            original_move = self.move_ids[0] if self.move_ids else False

            if original_move:
                debit_move.write({
                    'l10n_do_ecf_modification_code': self.l10n_do_ecf_modification_code or '1',
                    'l10n_do_origin_ncf': original_move.name,
                })

        return res
