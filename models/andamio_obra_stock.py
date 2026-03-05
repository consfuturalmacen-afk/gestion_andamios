from odoo import api, fields, models


class AndamioObraStock(models.Model):
    _name = "andamio.obra.stock"
    _description = "Stock de Piezas por Obra"
    _order = "obra_id, pieza_id"

    obra_id = fields.Many2one("andamio.obra", string="Obra", required=True, ondelete="cascade")
    pieza_id = fields.Many2one("andamio.pieza", string="Pieza", required=True, ondelete="cascade")
    cantidad = fields.Float(string="Cantidad en Obra", default=0.0)
    stock_wh = fields.Float(
        string="Stock en WH/Stock",
        related="pieza_id.stock_total",
        readonly=True,
        store=True,
        group_operator="max",
    )

    _sql_constraints = [
        (
            "andamio_obra_stock_unique",
            "unique(obra_id, pieza_id)",
            "Ya existe un registro de stock para esta pieza en la obra.",
        )
    ]

    @api.model
    def _sync_from_quants(self, obras=None):
        """Synchronize obra stock ledger from physical quants.

        This makes `andamio.obra.stock` a projection of real stock,
        avoiding drift between movement docs and inventory.
        """
        obra_model = self.env["andamio.obra"]
        pieza_model = self.env["andamio.pieza"]

        if obras is None:
            obras = obra_model.search([])
        else:
            obras = obras.filtered(lambda o: o.ubicacion_id)

        piezas = pieza_model.search([("product_id", "!=", False)])
        if not piezas:
            self.search([]).unlink()
            return

        pieza_by_product = {pieza.product_id.id: pieza for pieza in piezas}
        existing = self.search([("obra_id", "in", obras.ids)])
        existing_map = {(rec.obra_id.id, rec.pieza_id.id): rec for rec in existing}
        keep_keys = set()

        for obra in obras:
            location = obra.ubicacion_id
            if not location:
                continue
            quants = self.env["stock.quant"].search(
                [
                    ("location_id", "child_of", location.id),
                    ("product_id", "in", list(pieza_by_product.keys())),
                    ("quantity", "!=", 0),
                ]
            )
            qty_by_pieza = {}
            for quant in quants:
                pieza = pieza_by_product.get(quant.product_id.id)
                if not pieza:
                    continue
                qty_by_pieza[pieza.id] = qty_by_pieza.get(pieza.id, 0.0) + quant.quantity

            for pieza_id, qty in qty_by_pieza.items():
                if qty <= 0:
                    continue
                key = (obra.id, pieza_id)
                keep_keys.add(key)
                rec = existing_map.get(key)
                if rec:
                    rec.cantidad = qty
                else:
                    self.create({"obra_id": obra.id, "pieza_id": pieza_id, "cantidad": qty})

        stale = existing.filtered(lambda rec: (rec.obra_id.id, rec.pieza_id.id) not in keep_keys)
        if stale:
            stale.unlink()
