# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import requests
import base64
from lxml import etree

_logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend
    from signxml import XMLSigner, methods
except ImportError:
    XMLSigner = None
    pkcs12 = None


class AccountMove(models.Model):
    _inherit = "account.move"

    # ==========================================================
    # CAMPOS FISCALES TRADICIONALES (606, 607, 608)
    # ==========================================================
    l10n_do_expense_type = fields.Selection(
        selection=lambda self: self.env["res.partner"]._get_l10n_do_expense_type(
        ),
        string="Tipo de Costo y Gasto",
        compute="_compute_l10n_do_expense_type",
        store=True, readonly=False,
    )
    l10n_do_income_type = fields.Selection(
        selection=[
            ("01", _("01 - Ingresos por Operaciones")),
            ("02", _("02 - Ingresos Financieros")),
            ("03", _("03 - Ingresos Extraordinarios")),
            ("04", _("04 - Ingresos Arrendamientos")),
            ("05", _("05 - Ingresos por Venta de Activo Depreciable")),
            ("06", _("06 - Otros Ingresos")),
        ],
        string="Tipo de Ingreso", default="01", copy=False,
    )
    l10n_do_cancellation_type = fields.Selection(
        selection=[
            ("01", _("01 - Deterioro de Factura Pre-impresa")),
            ("02", _("02 - Errores de Impresión (Factura Pre-impresa)")),
            ("03", _("03 - Impresión Defectuosa")),
            ("04", _("04 - Corrección de la Información")),
            ("05", _("05 - Cambio de Productos")),
            ("06", _("06 - Devolución de Productos")),
            ("07", _("07 - Omisión de Productos")),
            ("08", _("08 - Errores en Secuencia de NCF")),
            ("09", _("09 - Por Cese de Operaciones")),
            ("10", _("10 - Pérdida o Hurto de Talonarios")),
        ],
        string="Tipo de Anulación", copy=False,
    )
    l10n_do_origin_ncf = fields.Char(string="NCF Origen", copy=False)
    l10n_do_ecf_modification_code = fields.Selection([
        ("1", "01 - Anulación Total"),
        ("2", "02 - Corrección de Texto"),
        ("3", "03 - Corrección de Monto"),
        ("4", "04 - Reemplazo de NCF"),
        ("5", "05 - Referencia a otro documento"),
    ], string="Código de Modificación e-CF", copy=False)

    # ==========================================================
    # CAMPOS DE FACTURACIÓN ELECTRÓNICA (e-CF)
    # ==========================================================
    l10n_do_ecf_send_state = fields.Selection([
        ('to_send', 'Pendiente de Envío'),
        ('sent', 'Enviado (Esperando Respuesta)'),
        ('delivered_accepted', 'Aceptado por DGII'),
        ('delivered_rejected', 'Rechazado por DGII')
    ], string="Estado e-CF DGII", default='to_send', copy=False, tracking=True)

    l10n_do_ecf_trackid = fields.Char(
        "Track ID DGII", copy=False, tracking=True)
    l10n_do_ecf_security_code = fields.Char(
        "Código de Seguridad (RI)", copy=False)
    l10n_do_ecf_qr_string = fields.Char(
        "URL del Código QR", compute="_compute_ecf_qr_string")

    # ==========================================================
    # METODOS COMPUTADOS Y DE INTERFAZ
    # ==========================================================
    @api.depends("partner_id")
    def _compute_l10n_do_expense_type(self):
        for move in self:
            if move.partner_id and move.partner_id.l10n_do_expense_type:
                move.l10n_do_expense_type = move.partner_id.l10n_do_expense_type

    @api.depends('l10n_do_ecf_security_code', 'state', 'name', 'amount_total_signed')
    def _compute_ecf_qr_string(self):
        for move in self:
            if move.l10n_do_ecf_security_code and move.company_id.vat and move.partner_id.vat:
                base_url = "https://ecf.dgii.gov.do/ecf/consultatimbre" if move.company_id.l10n_do_ecf_env == 'prod' else "https://ecf.dgii.gov.do/testecf/consultatimbre"
                rnc_em = move.company_id.vat.replace('-', '')
                rnc_co = move.partner_id.vat.replace('-', '')
                monto = f"{abs(move.amount_total_signed):.2f}"
                move.l10n_do_ecf_qr_string = f"{base_url}?RncEmisor={rnc_em}&RncComprador={rnc_co}&eNCF={move.name}&MontoTotal={monto}&CodigoSeguridad={move.l10n_do_ecf_security_code}"
            else:
                move.l10n_do_ecf_qr_string = False

    def button_cancel(self):
        do_invoices = self.filtered(
            lambda m: m.country_code == 'DO' and m.l10n_latam_use_documents and m.state == 'posted')
        if do_invoices:
            # Obligamos a usar el wizard para capturar el motivo de anulación
            return self.env.ref("l10n_do_fiscal_ecf.action_account_move_cancel").read()[0]
        return super().button_cancel()

    def _post(self, soft=True):
        res = super(AccountMove, self)._post(soft)
        # Auto-enviar e-CF al publicar la factura
        for move in self.filtered(lambda m: m.country_code == 'DO' and m.l10n_latam_use_documents):
            if move.company_id.l10n_do_ecf_issuer and move.l10n_latam_document_type_id.l10n_do_ncf_type.startswith('e-'):
                move.action_send_ecf_to_dgii()
        return res

    # ==========================================================
    # LOGICA CORE: FACTURACIÓN ELECTRÓNICA
    # ==========================================================
    def _generate_ecf_xml(self):
        self.ensure_one()
        nsmap = {None: 'http://dgii.gov.do/empresa/facturacion/ecf'}
        ecf_root = etree.Element('e-CF', nsmap=nsmap)

        encabezado = etree.SubElement(ecf_root, 'Encabezado')
        etree.SubElement(encabezado, 'Version').text = '1.0'

        id_doc = etree.SubElement(encabezado, 'IdDoc')
        etree.SubElement(
            id_doc, 'Tipoe-CF').text = self.l10n_latam_document_type_id.l10n_do_ncf_type[-2:]
        etree.SubElement(id_doc, 'e-NCF').text = self.name
        etree.SubElement(
            id_doc, 'FechaEmision').text = self.invoice_date.strftime('%d-%m-%Y')
        etree.SubElement(id_doc, 'TipoPago').text = getattr(
            self.journal_id, 'l10n_do_payment_form', '01') or '01'

        emisor = etree.SubElement(encabezado, 'Emisor')
        etree.SubElement(
            emisor, 'RNCEmisor').text = self.company_id.vat.replace('-', '')
        etree.SubElement(
            emisor, 'RazonSocialEmisor').text = self.company_id.name[:150]
        etree.SubElement(
            emisor, 'FechaEmision').text = self.invoice_date.strftime('%d-%m-%Y')

        comprador = etree.SubElement(encabezado, 'Comprador')
        etree.SubElement(
            comprador, 'RNCComprador').text = self.partner_id.vat.replace('-', '')
        etree.SubElement(
            comprador, 'RazonSocialComprador').text = self.partner_id.name[:150]

        totales = etree.SubElement(encabezado, 'Totales')
        etree.SubElement(
            totales, 'MontoTotal').text = f"{abs(self.amount_total_signed):.2f}"
        etree.SubElement(
            totales, 'MontoGravadoTotal').text = f"{abs(self.amount_untaxed_signed):.2f}"
        etree.SubElement(
            totales, 'TotalITBIS').text = f"{sum(self.invoice_line_ids.mapped('l10n_do_itbis_amount')):.2f}"

        detalles = etree.SubElement(ecf_root, 'DetallesItems')
        line_number = 1
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            item = etree.SubElement(detalles, 'Item')
            etree.SubElement(item, 'NumeroLinea').text = str(line_number)
            etree.SubElement(item, 'NombreItem').text = line.name[:80]
            etree.SubElement(
                item, 'CantidadItem').text = f"{line.quantity:.2f}"
            etree.SubElement(
                item, 'PrecioUnitarioItem').text = f"{line.price_unit:.2f}"
            etree.SubElement(
                item, 'MontoItem').text = f"{(line.quantity * line.price_unit):.2f}"

            if line.l10n_do_itbis_amount > 0:
                tabla_imp = etree.SubElement(item, 'TablaImpuestos')
                imp = etree.SubElement(tabla_imp, 'Impuesto')
                etree.SubElement(imp, 'TipoImpuesto').text = '1'
                etree.SubElement(
                    imp, 'MontoImpuesto').text = f"{line.l10n_do_itbis_amount:.2f}"
            line_number += 1

        if self.move_type in ['out_refund', 'in_refund'] and self.l10n_do_origin_ncf:
            ref = etree.SubElement(ecf_root, 'InformacionReferencia')
            etree.SubElement(
                ref, 'NCFModificado').text = self.l10n_do_origin_ncf
            etree.SubElement(
                ref, 'CodigoModificacion').text = self.l10n_do_ecf_modification_code or '1'

        return etree.tostring(ecf_root, pretty_print=True, xml_declaration=True, encoding='UTF-8')

    def action_send_ecf_to_dgii(self):
        for move in self:
            if move.l10n_do_ecf_send_state in ('sent', 'delivered_accepted'):
                continue

            company = move.company_id
            if not company.l10n_do_ecf_token:
                company.action_dgii_authenticate()

            try:
                raw_xml = move._generate_ecf_xml()
                root = etree.fromstring(raw_xml)

                cert_data = base64.b64decode(company.l10n_do_ecf_certificate)
                password = company.l10n_do_ecf_cert_password.encode('utf-8')
                private_key, certificate, _ = pkcs12.load_key_and_certificates(
                    cert_data, password, backend=default_backend())

                signer = XMLSigner(
                    method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256")
                signed_root = signer.sign(
                    root, key=private_key, cert=certificate)

                # Extraer código de seguridad (RI)
                sig_node = signed_root.find(
                    './/{http://www.w3.org/2000/09/xmldsig#}SignatureValue')
                if sig_node is not None and sig_node.text:
                    move.l10n_do_ecf_security_code = sig_node.text[:6]

                signed_xml_str = etree.tostring(
                    signed_root, xml_declaration=True, encoding='UTF-8')

                url = "https://ecf.dgii.gov.do/ecf/recepcion/api/recepcion/v1/fe" if company.l10n_do_ecf_env == 'prod' else "https://ecf.dgii.gov.do/testecf/recepcion/api/recepcion/v1/fe"
                headers = {
                    'Authorization': f'Bearer {company.l10n_do_ecf_token}', 'Accept': 'application/json'}
                filename = f"{company.vat.replace('-', '')}_{move.name}.xml"
                files = {'xml': (filename, signed_xml_str, 'text/xml')}

                res = requests.post(url, headers=headers,
                                    files=files, timeout=20)
                data = res.json()

                if res.status_code == 200 and 'trackId' in data:
                    move.write({'l10n_do_ecf_trackid': data.get(
                        'trackId'), 'l10n_do_ecf_send_state': 'sent'})
                    move.message_post(
                        body=_("e-CF enviado. Track ID: %s") % data.get('trackId'))
                else:
                    move.message_post(body=_("Rechazo DGII: %s") % res.text)

            except Exception as e:
                move.message_post(body=_("Error enviando e-CF: %s") % str(e))

    @api.model
    def _cron_check_ecf_status(self):
        moves = self.search(
            [('l10n_do_ecf_send_state', '=', 'sent'), ('l10n_do_ecf_trackid', '!=', False)])
        for move in moves:
            company = move.company_id
            if not company.l10n_do_ecf_token:
                company.action_dgii_authenticate()

            base_url = 'https://ecf.dgii.gov.do/ecf/consultatrackid/api/consultatrackid' if company.l10n_do_ecf_env == 'prod' else 'https://ecf.dgii.gov.do/testecf/consultatrackid/api/consultatrackid'
            url = f"{base_url}/{move.l10n_do_ecf_trackid}"
            headers = {'Authorization': f'Bearer {company.l10n_do_ecf_token}',
                       'Accept': 'application/json'}

            try:
                res = requests.get(url, headers=headers, timeout=15)
                if res.status_code == 401:
                    company.l10n_do_ecf_token = False
                    continue

                data = res.json()
                estado = data.get('estado')

                if estado in ['Aceptado', 'Aprobado']:
                    move.l10n_do_ecf_send_state = 'delivered_accepted'
                    move.message_post(body=_("✅ e-CF Aceptado por DGII."))
                elif estado == 'Rechazado':
                    errs = "<br/>".join(
                        [f"{m.get('codigo')}: {m.get('mensaje')}" for m in data.get('mensajes', [])])
                    move.l10n_do_ecf_send_state = 'delivered_rejected'
                    move.message_post(
                        body=_("❌ e-CF Rechazado.<br/>%s") % errs)

            except Exception as e:
                _logger.error("Error consultando TrackID %s: %s",
                              move.l10n_do_ecf_trackid, e)
