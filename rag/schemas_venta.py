"""Esquemas Pydantic para extraer una venta desde el contexto RAG."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProductoVendido(BaseModel):
    nombre: str = Field(description="Nombre del producto vendido")
    cantidad: Optional[float] = Field(default=None, description="Cantidad de unidades")
    precio_unitario: Optional[float] = Field(
        default=None, description="Precio por unidad si consta en el contexto"
    )
    subtotal: Optional[float] = Field(
        default=None, description="Subtotal de la línea si consta en el contexto"
    )


class VentaEstructurada(BaseModel):
    dia: Optional[str] = Field(
        default=None,
        description="Fecha de la venta si aparece (p. ej. YYYY-MM-DD)",
    )
    vendedor: Optional[str] = Field(
        default=None, description="Nombre del vendedor o empleado"
    )
    persona_atendida: Optional[str] = Field(
        default=None,
        description="Cliente o persona atendida (comprador)",
    )
    productos_vendidos: list[ProductoVendido] = Field(
        default_factory=list,
        description="Líneas de producto de la venta",
    )
    total_venta: Optional[float] = Field(
        default=None,
        description=(
            "Total de la jornada del vendedor si el texto lo indica; "
            "si solo aplica una línea de producto, puede omitirse o igualar al subtotal."
        ),
    )


class ListadoVentas(BaseModel):
    ventas: list[VentaEstructurada] = Field(
        default_factory=list,
        description=(
            "Todas las ventas del contexto que respondan a la pregunta. "
            "Si hay varios vendedores o varias ventas del mismo producto (ej. varios iPhone), "
            "incluye un elemento por cada venta; no omitas filas relevantes."
        ),
    )
