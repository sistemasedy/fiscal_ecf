# -*- coding: utf-8 -*-
from re import compile
from odoo import models, fields, _
from odoo.exceptions import ValidationError


class L10nLatamDocumentType(models.Model):
    _inherit = "l10n_latam.document.type"

    def _get_l10n_do_ncf_types(self):
        """Retorna los tipos de NCF y sus secuencias (B o E)"""
        return [
            ("fiscal", "01"),
            ("consumer", "02"),
            ("debit_note", "03"),
            ("credit_note", "04"),
            ("informal", "11"),
            ("unique", "12"),
            ("minor", "13"),
            ("special", "14"),
            ("governmental", "15"),
            ("export", "16"),
            ("exterior", "17"),
            # Facturación Electrónica (e-CF)
            ("e-fiscal", "31"),
            ("e-consumer", "32"),
            ("e-debit_note", "33"),
            ("e-credit_note", "34"),
            ("e-informal", "41"),
            ("e-minor", "43"),
            ("e-special", "44"),
            ("e-governmental", "45"),
            ("e-export", "46"),
            ("e-exterior", "47"),
        ]

    l10n_do_ncf_type = fields.Selection(
        selection="_get_l10n_do_ncf_types",
        string="Tipo de NCF (DGII)",
        help="Clasificación de la DGII para identificar la operación.",
    )

    internal_type = fields.Selection(
        selection_add=[
            ("in_invoice", "Factura de Proveedor"),
            ("in_credit_note", "Nota de Crédito de Proveedor"),
            ("in_debit_note", "Nota de Débito de Proveedor"),
        ],
        ondelete={
            "in_invoice": "cascade",
            "in_credit_note": "cascade",
            "in_debit_note": "cascade",
        },
    )

    is_vat_required = fields.Boolean(
        string="Requiere RNC/Cédula",
        default=False,
    )

    def _format_document_number(self, document_number):
        """
        Valida que el NCF digitado tenga la estructura correcta (11 o 13 caracteres)
        y formatea el prefijo.
        """
        self.ensure_one()
        if self.country_id.code != "DO":
            return super()._format_document_number(document_number)

        if not document_number:
            return False

        # Regex para validar Facturación Electrónica (E + 12 dígitos) o Tradicional (B + 10 dígitos)
        ncf_type_code = dict(self._get_l10n_do_ncf_types())[
            self.l10n_do_ncf_type]
        regex = r"^(P?((?=.{13})E)type(\d{10})|(((?=.{11})B))type(\d{8}))$".replace(
            "type", ncf_type_code)

        pattern = compile(regex)

        # Limpiar espacios
        document_number = document_number.strip().upper()

        if not bool(pattern.match(document_number)):
            raise ValidationError(
                _("El comprobante '%s' no tiene la estructura correcta para el tipo '%s'. "
                  "Recuerde: Tradicional inicia con B (11 caracteres), Electrónico inicia con E (13 caracteres).")
                % (document_number, self.name)
            )

        return document_number
