from odoo import api, fields, models


class AndamioObra(models.Model):
    _name = "andamio.obra"
    _description = "Obra"

    ubicacion_id = fields.Many2one(
        "stock.location",
        string="Ubicación Interna",
        domain=[("usage", "=", "internal")],
        required=True,
    )
    name = fields.Char(
        string="Obra",
        related="ubicacion_id.complete_name",
        store=True,
        readonly=True,
    )
    ubicacion = fields.Char(
        string="Ubicación",
        related="ubicacion_id.complete_name",
        store=True,
        readonly=True,
    )
    encargado_id = fields.Many2one("res.partner", string="Encargado")
    movimiento_ids = fields.One2many("andamio.movimiento", "obra_id", string="Movimientos")
    stock_por_pieza_ids = fields.One2many("andamio.obra.stock", "obra_id", string="Stock por Pieza")
    stock_move_ids = fields.Many2many(
        "stock.move",
        string="Movimientos de Stock",
        compute="_compute_stock_move_ids",
    )
    piezas_en_obra = fields.Char(string="Piezas en Obra", compute="_compute_resumen_obras")
    total_andamios_obra = fields.Float(string="Total Andamios en Obra", compute="_compute_resumen_obras")

    @api.depends("movimiento_ids.stock_move_ids", "ubicacion_id")
    def _compute_stock_move_ids(self):
        for obra in self:
            if not obra.ubicacion_id:
                obra.stock_move_ids = self.env["stock.move"]
                continue
            obra.stock_move_ids = self.env["stock.move"].search(
                [
                    ("state", "=", "done"),
                    "|",
                    ("location_id", "child_of", obra.ubicacion_id.id),
                    ("location_dest_id", "child_of", obra.ubicacion_id.id),
                ]
            )

    @api.depends("stock_por_pieza_ids.cantidad", "stock_por_pieza_ids.pieza_id")
    def _compute_resumen_obras(self):
        self.env["andamio.obra.stock"]._sync_from_quants(obras=self)
        for obra in self:
            lineas = obra.stock_por_pieza_ids.filtered(lambda l: l.cantidad > 0)
            obra.total_andamios_obra = sum(lineas.mapped("cantidad"))
            obra.piezas_en_obra = (
                ", ".join(
                    f"{linea.pieza_id.display_name}: {linea.cantidad:g}"
                    for linea in lineas.sorted(key=lambda l: l.pieza_id.display_name)
                )
                if lineas
                else "Sin piezas en obra"
            )
