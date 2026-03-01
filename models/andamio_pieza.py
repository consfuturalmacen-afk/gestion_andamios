from odoo import api, fields, models


class AndamioPieza(models.Model):
    _name = "andamio.pieza"
    _description = "Pieza de Andamio"

    name = fields.Char(string="Nombre", required=True)
    codigo = fields.Char(string="Código", required=True, copy=False)
    product_id = fields.Many2one(
        "product.product",
        string="Producto de Inventario",
        required=True,
        domain=[("type", "=", "product")],
    )
    image_1920 = fields.Image(string="Imagen")
    stock_total = fields.Float(
        string="Stock en WH/Stock",
        compute="_compute_stock_total",
        digits="Product Unit of Measure",
    )

    _sql_constraints = [
        ("andamio_pieza_codigo_unique", "unique(codigo)", "El código debe ser único."),
    ]

    @api.depends("product_id")
    def _compute_stock_total(self):
        stock_location = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        for pieza in self:
            if not pieza.product_id or not stock_location:
                pieza.stock_total = 0.0
                continue
            quants = self.env["stock.quant"].search([
                ("product_id", "=", pieza.product_id.id),
                ("location_id", "=", stock_location.id),
            ])
            pieza.stock_total = sum(quants.mapped("available_quantity"))
