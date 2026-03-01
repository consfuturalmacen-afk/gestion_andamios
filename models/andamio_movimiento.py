from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class AndamioMovimiento(models.Model):
    _name = "andamio.movimiento"
    _description = "Movimiento de Andamios"

    obra_id = fields.Many2one("andamio.obra", string="Obra", required=True)
    fecha_entrega = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    tipo_movimiento = fields.Selection(
        [("salida", "Salida a Obra"), ("devolucion", "Devolución a Almacén")],
        string="Tipo",
        required=True,
        default="salida",
    )
    lineas_ids = fields.One2many("andamio.movimiento.linea", "movimiento_id", string="Líneas")
    estado = fields.Selection(
        [("borrador", "Borrador"), ("en_obra", "En Obra"), ("devuelto", "Devuelto")],
        string="Estado",
        default="borrador",
        required=True,
    )
    stock_move_ids = fields.One2many("stock.move", "andamio_movimiento_id", string="Movimientos Stock")


    def _get_location_qty(self, product, location, use_available=True):
        quants = self.env["stock.quant"].search([
            ("product_id", "=", product.id),
            ("location_id", "child_of", location.id),
        ])
        field_name = "available_quantity" if use_available else "quantity"
        return sum(quants.mapped(field_name))

    def write(self, vals):
        if "tipo_movimiento" in vals:
            bloqueados = self.filtered(lambda mov: mov.estado != "borrador")
            if bloqueados:
                raise UserError(
                    _("No se puede cambiar el tipo de movimiento fuera de estado borrador.")
                )
        return super().write(vals)

    def action_confirmar(self):
        stock_location = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        if not stock_location:
            raise UserError(_("No se encontró la ubicación WH/Stock."))

        for movimiento in self:
            if movimiento.estado != "borrador":
                continue
            if not movimiento.lineas_ids:
                raise UserError(_("Debe agregar al menos una línea de piezas."))
            if not movimiento.obra_id.ubicacion_id:
                raise UserError(_("La obra debe tener una ubicación interna configurada."))

            if movimiento.tipo_movimiento == "salida":
                location_id = stock_location
                location_dest_id = movimiento.obra_id.ubicacion_id
                nuevo_estado = "en_obra"
            else:
                location_id = movimiento.obra_id.ubicacion_id
                location_dest_id = stock_location
                nuevo_estado = "devuelto"

            for linea in movimiento.lineas_ids:
                if linea.cantidad <= 0:
                    raise UserError(_("La cantidad debe ser mayor que cero."))
                if not linea.pieza_id.product_id:
                    raise UserError(
                        _("La pieza %s no tiene producto de inventario.")
                        % linea.pieza_id.display_name
                    )

                use_available = movimiento.tipo_movimiento == "salida"
                disponible = movimiento._get_location_qty(
                    linea.pieza_id.product_id,
                    location_id,
                    use_available=use_available,
                )
                if disponible < linea.cantidad:
                    raise UserError(
                        _(
                            "Stock insuficiente para %s en %s. Disponible: %s, solicitado: %s"
                        )
                        % (
                            linea.pieza_id.display_name,
                            location_id.display_name,
                            disponible,
                            linea.cantidad,
                        )
                    )

                move = self.env["stock.move"].create(
                    {
                        "product_id": linea.pieza_id.product_id.id,
                        "product_uom_qty": linea.cantidad,
                        "product_uom": linea.pieza_id.product_id.uom_id.id,
                        "location_id": location_id.id,
                        "location_dest_id": location_dest_id.id,
                        "state": "draft",
                        "andamio_movimiento_id": movimiento.id,
                    }
                )
                move._action_confirm()
                move._action_assign()
                if move.state != "assigned":
                    raise UserError(
                        _("No se pudo reservar stock para %s. Estado actual: %s")
                        % (linea.pieza_id.display_name, move.state)
                    )
                move._action_done()

            movimiento.estado = nuevo_estado

    def action_borrador(self):
        for rec in self:
            rec.estado = "borrador"


class AndamioMovimientoLinea(models.Model):
    _name = "andamio.movimiento.linea"
    _description = "Línea de Movimiento de Andamios"

    movimiento_id = fields.Many2one(
        "andamio.movimiento", string="Movimiento", required=True, ondelete="cascade"
    )
    pieza_id = fields.Many2one("andamio.pieza", string="Pieza", required=True)
    cantidad = fields.Float(string="Cantidad", required=True, default=1.0)

    _sql_constraints = [
        (
            "andamio_movimiento_linea_unique_pieza",
            "unique(movimiento_id, pieza_id)",
            "No puede repetir la misma pieza en un movimiento.",
        ),
    ]

    @api.constrains("cantidad")
    def _check_cantidad_positiva(self):
        for linea in self:
            if linea.cantidad <= 0:
                raise ValidationError(_("La cantidad en líneas debe ser mayor que cero."))


class StockMove(models.Model):
    _inherit = "stock.move"

    andamio_movimiento_id = fields.Many2one(
        "andamio.movimiento", string="Movimiento Andamio", index=True
    )
