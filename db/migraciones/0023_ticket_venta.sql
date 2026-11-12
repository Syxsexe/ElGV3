-- 0023_ticket_venta.sql — Mensaje al pie del ticket de venta.
--
-- El ticket que se le entrega al cliente termina con un texto que el negocio
-- edita en Configuración (agradecimiento, redes, horario…). Vacío = sin texto.

ALTER TABLE empresa
    ADD COLUMN mensaje_ticket text DEFAULT '¡Gracias por su compra!'
        CHECK (length(mensaje_ticket) <= 300);
COMMENT ON COLUMN empresa.mensaje_ticket IS 'Texto al pie del ticket de venta (null = sin texto).';
