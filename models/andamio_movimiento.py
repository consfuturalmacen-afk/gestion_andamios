from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class AndamioMovimiento(models.Model):
    _name = "andamio.movimiento"
    _description = "Movimiento de Andamios"

    obra_id = fields.Many2one("andamio.obra", string="Obra Origen", required=True)
    obra_destino_id = fields.Many2one(
        "andamio.obra",
        string="Obra Destino",
        domain="[('id', '!=', obra_id)]",
    )
    fecha_entrega = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    tipo_movimiento = fields.Selection(
        [
            ("salida", "Salida a Obra"),
            ("devolucion", "Devolución a Almacén"),
            ("traslado", "Traslado entre Obras"),
        ],
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

    def _get_location_qty(self, product, location, use_available=True, include_children=True):
        location_domain = ("location_id", "child_of", location.id) if include_children else ("location_id", "=", location.id)
        quants = self.env["stock.quant"].search(
            [("product_id", "=", product.id), location_domain]
        )
        field_name = "available_quantity" if use_available else "quantity"
        return sum(quants.mapped(field_name))

    def _get_stock_sitio(self, pieza, obra=None):
        if obra:
            registro = self.env["andamio.obra.stock"].search(
                [("obra_id", "=", obra.id), ("pieza_id", "=", pieza.id)], limit=1
            )
            return registro.cantidad if registro else 0.0
        stock_location = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        if not stock_location or not pieza.product_id:
            return 0.0
        return self._get_location_qty(
            pieza.product_id,
            stock_location,
            use_available=False,
            include_children=False,
        )

    def _find_source_location(self, base_location, product, required_qty):
        quant = self.env["stock.quant"].search(
            [
                ("product_id", "=", product.id),
                ("location_id", "child_of", base_location.id),
                ("quantity", ">", 0),
            ],
            order="quantity desc",
            limit=1,
        )
        if quant and quant.quantity >= required_qty:
            return quant.location_id
        return base_location

    def _get_source_chunks(self, base_location, product, qty):
        """Return source locations and quantities to avoid forcing negatives.

        For returns/transfers we can have stock spread across child locations of
        the obra. This method splits the requested quantity across the real
        locations with positive quants.
        """
        remaining = qty
        chunks = []
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", product.id),
                ("location_id", "child_of", base_location.id),
                ("quantity", ">", 0),
            ],
            order="quantity desc",
        )
        for quant in quants:
            if remaining <= 0:
                break
            take = min(quant.quantity, remaining)
            if take > 0:
                chunks.append((quant.location_id, take))
                remaining -= take

        if remaining > 0:
            # Keep behavior resilient in desynchronized cases by topping up the
            # base location and using it as final source.
            self._ensure_physical_stock(product, base_location, remaining)
            chunks.append((base_location, remaining))

        return chunks

    @api.constrains("tipo_movimiento", "obra_destino_id", "obra_id")
    def _check_obra_destino_traslado(self):
        for mov in self:
            if mov.tipo_movimiento == "traslado" and not mov.obra_destino_id:
                raise ValidationError(_("Debe indicar una Obra Destino para traslados."))
            if mov.tipo_movimiento == "traslado" and mov.obra_destino_id == mov.obra_id:
                raise ValidationError(_("La Obra Destino debe ser distinta a la Obra Origen."))

    def _apply_obra_stock(self, obra, pieza, delta):
        stock_model = self.env["andamio.obra.stock"]
        registro = stock_model.search(
            [("obra_id", "=", obra.id), ("pieza_id", "=", pieza.id)], limit=1
        )
        if not registro:
            if delta < 0:
                raise UserError(
                    _("No hay stock registrado de %s en la obra %s.")
                    % (pieza.display_name, obra.display_name)
                )
            registro = stock_model.create(
                {"obra_id": obra.id, "pieza_id": pieza.id, "cantidad": 0.0}
            )
        nuevo = registro.cantidad + delta
        if nuevo < 0:
            raise UserError(
                _("Stock insuficiente para %s en %s. Disponible: %s, solicitado: %s")
                % (pieza.display_name, obra.display_name, registro.cantidad, abs(delta))
            )
        registro.cantidad = nuevo

    def _ensure_physical_stock(self, product, location, required_qty):
        physical_qty = self._get_location_qty(
            product,
            location,
            use_available=False,
            include_children=True,
        )
        if physical_qty >= required_qty:
            return
        self.env["stock.quant"]._update_available_quantity(
            product,
            location,
            required_qty - physical_qty,
        )

    def _set_move_done_qty(self, move, qty):
        if hasattr(move, "_set_quantity_done"):
            move._set_quantity_done(qty)
            return

        if move.move_line_ids:
            for line in move.move_line_ids:
                if "quantity" in line._fields:
                    line.quantity = qty
                elif "qty_done" in line._fields:
                    line.qty_done = qty
            return

        values = {
            "move_id": move.id,
            "product_id": move.product_id.id,
            "product_uom_id": move.product_uom.id,
            "location_id": move.location_id.id,
            "location_dest_id": move.location_dest_id.id,
        }
        if "quantity" in self.env["stock.move.line"]._fields:
            values["quantity"] = qty
        elif "qty_done" in self.env["stock.move.line"]._fields:
            values["qty_done"] = qty
        self.env["stock.move.line"].create(values)

    def write(self, vals):
        if "tipo_movimiento" in vals:
            bloqueados = self.filtered(lambda mov: mov.estado != "borrador")
            if bloqueados:
                raise UserError(_("No se puede cambiar el tipo de movimiento fuera de estado borrador."))
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
                raise UserError(_("La obra origen debe tener una ubicación interna configurada."))

            if movimiento.tipo_movimiento == "salida":
                default_source_location = stock_location
                location_dest_id = movimiento.obra_id.ubicacion_id
                nuevo_estado = "en_obra"
            elif movimiento.tipo_movimiento == "devolucion":
                default_source_location = movimiento.obra_id.ubicacion_id
                location_dest_id = stock_location
                nuevo_estado = "devuelto"
            else:
                if not movimiento.obra_destino_id or not movimiento.obra_destino_id.ubicacion_id:
                    raise UserError(_("Debe indicar una obra destino con ubicación interna."))
                default_source_location = movimiento.obra_id.ubicacion_id
                location_dest_id = movimiento.obra_destino_id.ubicacion_id
                nuevo_estado = "en_obra"

            for linea in movimiento.lineas_ids:
                if linea.cantidad <= 0:
                    raise UserError(_("La cantidad debe ser mayor que cero."))
                if not linea.pieza_id.product_id:
                    raise UserError(_("La pieza %s no tiene producto de inventario.") % linea.pieza_id.display_name)

                linea.stock_origen_antes = self._get_stock_sitio(
                    linea.pieza_id,
                    obra=movimiento.obra_id if movimiento.tipo_movimiento != "salida" else None,
                )
                linea.stock_destino_antes = self._get_stock_sitio(
                    linea.pieza_id,
                    obra=movimiento.obra_destino_id if movimiento.tipo_movimiento == "traslado" else (
                        movimiento.obra_id if movimiento.tipo_movimiento == "salida" else None
                    ),
                )

                if movimiento.tipo_movimiento == "salida":
                    disponible = movimiento._get_location_qty(
                        linea.pieza_id.product_id,
                        default_source_location,
                        use_available=True,
                    )
                    if disponible < linea.cantidad:
                        raise UserError(
                            _("Stock insuficiente para %s en %s. Disponible: %s, solicitado: %s")
                            % (
                                linea.pieza_id.display_name,
                                default_source_location.display_name,
                                disponible,
                                linea.cantidad,
                            )
                        )
                elif movimiento.tipo_movimiento == "devolucion":
                    movimiento._apply_obra_stock(movimiento.obra_id, linea.pieza_id, -linea.cantidad)
                    movimiento._ensure_physical_stock(
                        linea.pieza_id.product_id,
                        default_source_location,
                        linea.cantidad,
                    )
                else:
                    movimiento._apply_obra_stock(movimiento.obra_id, linea.pieza_id, -linea.cantidad)
                    movimiento._apply_obra_stock(movimiento.obra_destino_id, linea.pieza_id, linea.cantidad)
                    movimiento._ensure_physical_stock(
                        linea.pieza_id.product_id,
                        default_source_location,
                        linea.cantidad,
                    )

                move_chunks = [(default_source_location, linea.cantidad)]
                if movimiento.tipo_movimiento in ("devolucion", "traslado"):
                    move_chunks = movimiento._get_source_chunks(
                        default_source_location,
                        linea.pieza_id.product_id,
                        linea.cantidad,
                    )

                for source_location, move_qty in move_chunks:
                    move = self.env["stock.move"].create(
                        {
                            "product_id": linea.pieza_id.product_id.id,
                            "product_uom_qty": move_qty,
                            "product_uom": linea.pieza_id.product_id.uom_id.id,
                            "location_id": source_location.id,
                            "location_dest_id": location_dest_id.id,
                            "state": "draft",
                            "andamio_movimiento_id": movimiento.id,
                        }
                    )
                    move._action_confirm()
                    move.with_context(allow_negative_stock=True)._action_assign()
                    if movimiento.tipo_movimiento in ("devolucion", "traslado"):
                        movimiento._set_move_done_qty(move, move_qty)
                        move.with_context(allow_negative_stock=True)._action_done()
                    else:
                        if move.state != "assigned":
                            raise UserError(
                                _("No se pudo reservar stock para %s. Estado actual: %s")
                                % (linea.pieza_id.display_name, move.state)
                            )
                        move._action_done()
                        movimiento._apply_obra_stock(movimiento.obra_id, linea.pieza_id, linea.cantidad)

                linea.stock_origen_despues = self._get_stock_sitio(
                    linea.pieza_id,
                    obra=movimiento.obra_id if movimiento.tipo_movimiento != "salida" else None,
                )
                linea.stock_destino_despues = self._get_stock_sitio(
                    linea.pieza_id,
                    obra=movimiento.obra_destino_id if movimiento.tipo_movimiento == "traslado" else (
                        movimiento.obra_id if movimiento.tipo_movimiento == "salida" else None
                    ),
                )

            movimiento.estado = nuevo_estado

    def action_borrador(self):
        for rec in self:
            rec.estado = "borrador"


class AndamioMovimientoLinea(models.Model):
    _name = "andamio.movimiento.linea"
    _description = "Línea de Movimiento de Andamios"

    movimiento_id = fields.Many2one("andamio.movimiento", string="Movimiento", required=True, ondelete="cascade")
    pieza_id = fields.Many2one("andamio.pieza", string="Pieza", required=True)
    cantidad = fields.Float(string="Cantidad", required=True, default=1.0)
    stock_origen_antes = fields.Float(string="Stock origen antes", readonly=True)
    stock_origen_despues = fields.Float(string="Stock origen después", readonly=True)
    stock_destino_antes = fields.Float(string="Stock destino antes", readonly=True)
    stock_destino_despues = fields.Float(string="Stock destino después", readonly=True)

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

    andamio_movimiento_id = fields.Many2one("andamio.movimiento", string="Movimiento Andamio", index=True)
