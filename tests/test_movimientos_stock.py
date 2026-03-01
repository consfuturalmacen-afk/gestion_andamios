from odoo.tests.common import TransactionCase


class TestMovimientosStock(TransactionCase):
    def setUp(self):
        super().setUp()
        self.stock_location = self.env.ref("stock.stock_location_stock")
        self.ubicacion_obra = self.env["stock.location"].create(
            {
                "name": "Obra Test",
                "usage": "internal",
                "location_id": self.stock_location.id,
            }
        )
        self.obra = self.env["andamio.obra"].create(
            {"name": "Obra Test", "ubicacion_id": self.ubicacion_obra.id}
        )
        self.product = self.env["product.product"].create(
            {"name": "Producto Andamio Test", "type": "product"}
        )
        self.pieza = self.env["andamio.pieza"].create(
            {
                "name": "Pieza Test",
                "codigo": "PZ-TEST-001",
                "product_id": self.product.id,
            }
        )

    def _crear_movimiento(self, tipo, cantidad):
        return self.env["andamio.movimiento"].create(
            {
                "obra_id": self.obra.id,
                "tipo_movimiento": tipo,
                "lineas_ids": [
                    (0, 0, {"pieza_id": self.pieza.id, "cantidad": cantidad})
                ],
            }
        )

    def test_no_permite_cantidad_cero(self):
        with self.assertRaises(Exception):
            self._crear_movimiento("salida", 0)

    def test_no_permite_pieza_duplicada_en_lineas(self):
        with self.assertRaises(Exception):
            self.env["andamio.movimiento"].create(
                {
                    "obra_id": self.obra.id,
                    "tipo_movimiento": "salida",
                    "lineas_ids": [
                        (0, 0, {"pieza_id": self.pieza.id, "cantidad": 1}),
                        (0, 0, {"pieza_id": self.pieza.id, "cantidad": 2}),
                    ],
                }
            )

    def test_no_permite_cambiar_tipo_fuera_borrador(self):
        mov = self._crear_movimiento("salida", 1)
        mov.estado = "en_obra"
        with self.assertRaises(Exception):
            mov.write({"tipo_movimiento": "devolucion"})


    def test_traslado_requiere_obra_destino(self):
        with self.assertRaises(Exception):
            self.env["andamio.movimiento"].create(
                {
                    "obra_id": self.obra.id,
                    "tipo_movimiento": "traslado",
                    "lineas_ids": [(0, 0, {"pieza_id": self.pieza.id, "cantidad": 1})],
                }
            )
