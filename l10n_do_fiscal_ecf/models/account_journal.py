# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import RedirectWarning, ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_l10n_do_payment_form(self):
        """ Retorna la lista de formas de pago permitidas por la DGII. """
        return [
            ("cash", _("Efectivo")),
            ("bank", _("Cheque / Transferencia")),
            ("card", _("Tarjeta de Crédito / Débito")),
            ("credit", _("A Crédito")),
            ("swap", _("Permuta")),
            ("bond", _("Bonos o Certificados de Regalo")),
            ("others", _("Otras Formas")),
        ]

    l10n_do_payment_form = fields.Selection(
        selection="_get_l10n_do_payment_form",
        string="Forma de Pago (DGII)",
        help="Requerido para el formato de envío 606 y la Facturación Electrónica.",
    )

    l10n_do_document_type_ids = fields.One2many(
        "l10n_do.account.journal.document_type",
        "journal_id",
        string="Tipos de Documentos Permitidos",
        copy=False,
    )

    @api.model
    def _get_l10n_do_ncf_types_data(self):
        """ Matriz de NCF según el tipo de contribuyente y si es emisión o recepción """
        return {
            "issued": {
                "taxpayer": ["fiscal"],
                "non_payer": ["consumer", "unique"],
                "nonprofit": ["fiscal"],
                "special": ["special"],
                "governmental": ["governmental"],
                "foreigner": ["export", "consumer"],
            },
            "received": {
                "taxpayer": ["fiscal"],
                "non_payer": ["informal", "minor"],
                "nonprofit": ["special", "governmental"],
                "special": ["fiscal", "special", "governmental"],
                "governmental": ["fiscal", "special", "governmental"],
                "foreigner": ["import", "exterior"],
            },
        }

    def _get_all_ncf_types(self, types_list, invoice=False):
        """
        Incluye los prefijos 'e-' (e-CF) si la empresa es emisora electrónica.
        """
        ecf_types = ["e-%s" %
                     d for d in types_list if d not in ("unique", "import")]

        if self._context.get("use_documents", False) or not invoice:
            return types_list + ecf_types

        # Si es un documento de compra a un consumidor final o extranjero
        if invoice.is_purchase_document() and invoice.partner_id.l10n_do_dgii_tax_payer_type in ("non_payer", "foreigner"):
            return ecf_types if self.company_id.l10n_do_ecf_issuer else types_list

        return types_list + ecf_types


class AccountJournalDocumentType(models.Model):
    _name = "l10n_do.account.journal.document_type"
    _description = "Tipo de Documento del Diario"

    journal_id = fields.Many2one(
        "account.journal", "Diario", required=True, readonly=True
    )
    l10n_latam_document_type_id = fields.Many2one(
        "l10n_latam.document.type", "Tipo de Documento", required=True, readonly=True
    )
    company_id = fields.Many2one(
        string="Compañía", related="journal_id.company_id", readonly=True
    )
