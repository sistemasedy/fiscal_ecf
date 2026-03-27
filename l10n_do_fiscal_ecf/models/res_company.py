# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import requests
import logging
from datetime import datetime, timedelta
from lxml import etree

_logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend
    from signxml import XMLSigner, methods
except ImportError:
    pkcs12 = None
    XMLSigner = None


class ResCompany(models.Model):
    _inherit = "res.company"

    # --- Configuraciones Generales DGII ---
    l10n_do_dgii_start_date = fields.Date("Fecha de Inicio de Actividades")
    l10n_do_default_client = fields.Selection(
        selection=[("non_payer", "Consumidor Final"),
                   ("taxpayer", "Crédito Fiscal")],
        default="non_payer",
        string="Cliente por Defecto",
    )
    l10n_do_ecf_issuer = fields.Boolean(
        "Es Emisor Electrónico (e-CF)",
        help="Al activar esto, se priorizan las secuencias que inician con 'E'.",
    )
    l10n_do_ecf_deferred_submissions = fields.Boolean(
        "Envíos Diferidos",
        help="Para contribuyentes autorizados a facturar fuera de línea.",
    )

    # --- Credenciales e-CF ---
    l10n_do_ecf_env = fields.Selection([
        ('cer', 'Certificación (Pruebas)'),
        ('prod', 'Producción')
    ], string="Entorno DGII", default='cer', required=True)

    l10n_do_ecf_certificate = fields.Binary(
        string="Certificado Digital (.p12)",
        copy=False,
    )
    l10n_do_ecf_cert_password = fields.Char(
        string="Contraseña del Certificado",
        copy=False,
        groups="base.group_system",
    )
    l10n_do_ecf_cert_is_valid = fields.Boolean(
        string="Certificado Válido",
        compute="_compute_cert_is_valid",
        store=True
    )

    # --- Tokens y Sesión ---
    l10n_do_ecf_token = fields.Char(string="Token Bearer DGII", copy=False)
    l10n_do_ecf_token_expires = fields.Datetime(
        string="Expiración del Token", copy=False)

    def _localization_use_documents(self):
        self.ensure_one()
        return True if self.country_id.code == "DO" else super()._localization_use_documents()

    @api.depends('l10n_do_ecf_certificate', 'l10n_do_ecf_cert_password')
    def _compute_cert_is_valid(self):
        for company in self:
            if not company.l10n_do_ecf_certificate or not company.l10n_do_ecf_cert_password or pkcs12 is None:
                company.l10n_do_ecf_cert_is_valid = False
                continue
            try:
                cert_data = base64.b64decode(company.l10n_do_ecf_certificate)
                password = company.l10n_do_ecf_cert_password.encode('utf-8')
                pkcs12.load_key_and_certificates(
                    cert_data, password, backend=default_backend())
                company.l10n_do_ecf_cert_is_valid = True
            except Exception:
                company.l10n_do_ecf_cert_is_valid = False

    def _get_dgii_api_url(self):
        self.ensure_one()
        if self.l10n_do_ecf_env == 'prod':
            return 'https://ecf.dgii.gov.do/ecf/autenticacion/api/autenticacion'
        return 'https://ecf.dgii.gov.do/testecf/autenticacion/api/autenticacion'

    def action_dgii_authenticate(self):
        self.ensure_one()
        if not self.l10n_do_ecf_cert_is_valid:
            raise UserError(
                _("Debe configurar un certificado digital válido y su contraseña."))
        if XMLSigner is None:
            raise UserError(_("La librería 'signxml' no está instalada."))

        base_url = self._get_dgii_api_url()

        # 1. Obtener Semilla
        try:
            seed_res = requests.get(f"{base_url}/semilla", timeout=10)
            seed_res.raise_for_status()
        except Exception as e:
            raise UserError(_("Error solicitando semilla a DGII:\n%s") % e)

        # 2. Firmar Semilla
        try:
            cert_data = base64.b64decode(self.l10n_do_ecf_certificate)
            password = self.l10n_do_ecf_cert_password.encode('utf-8')
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                cert_data, password, backend=default_backend()
            )
            root = etree.fromstring(seed_res.content)
            signer = XMLSigner(
                method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256")
            signed_root = signer.sign(root, key=private_key, cert=certificate)
            signed_xml_str = etree.tostring(
                signed_root, xml_declaration=True, encoding='UTF-8')
        except Exception as e:
            raise UserError(_("Error firmando la semilla:\n%s") % e)

        # 3. Validar Semilla y obtener Token
        try:
            files = {'xml': ('semilla_firmada.xml',
                             signed_xml_str, 'text/xml')}
            headers = {'accept': 'application/json'}
            auth_res = requests.post(
                f"{base_url}/validarsemilla", files=files, headers=headers, timeout=15)
            if auth_res.status_code != 200:
                raise UserError(
                    _("Firma rechazada por DGII:\n%s") % auth_res.text)

            response_data = auth_res.json()
        except requests.exceptions.RequestException as e:
            raise UserError(
                _("Error de comunicación enviando semilla:\n%s") % e)

        # 4. Guardar Token
        token = response_data.get('token')
        expires_str = response_data.get('expira')

        if token:
            self.l10n_do_ecf_token = token
            if expires_str:
                clean_date = expires_str.replace('T', ' ').replace('Z', '')
                self.l10n_do_ecf_token_expires = datetime.strptime(
                    clean_date, '%Y-%m-%d %H:%M:%S')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Éxito"),
                    'message': _("Token de DGII obtenido correctamente."),
                    'type': 'success',
                    'sticky': False,
                }
            }
        raise UserError(_("Respuesta inválida de la DGII: %s") % response_data)

    @api.model
    def _cron_dgii_authenticate_token(self):
        companies = self.search([('l10n_do_ecf_cert_is_valid', '=', True)])
        now = fields.Datetime.now()

        for company in companies:
            needs_renewal = False
            if not company.l10n_do_ecf_token or not company.l10n_do_ecf_token_expires:
                needs_renewal = True
            elif company.l10n_do_ecf_token_expires <= now + timedelta(minutes=10):
                needs_renewal = True

            if needs_renewal:
                try:
                    company.action_dgii_authenticate()
                except Exception as e:
                    _logger.error(
                        "Error renovando Token DGII para %s: %s", company.name, e)
