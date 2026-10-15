# XSM

Bot de trading sobre futuros perpetuos de criptomonedas. Cada lunes toma las 30 monedas con más volumen operado
en Bybit, compra las 6 que más subieron en el último mes y vende en corto las 6 que más bajaron, con el mismo
capital de cada lado. Gana si lo comprado rinde más que lo vendido, suba o baje el mercado. El nombre viene de
*cross-sectional momentum*, que es como se llama este enfoque en la literatura.

**Registro en vivo: [galoberrutti.github.io/xsm](https://galoberrutti.github.io/xsm/)**

Corre con una cuenta simulada, sin dinero real. Desde el 19 de octubre de 2026, cada cartera se publica en este
repositorio en el momento en que el bot la decide, y el resultado se calcula con los precios públicos de Bybit. El
código del bot no está acá: están sus decisiones y la forma de comprobar el resultado.

## Qué se publica

| archivo | qué tiene | cuándo |
|---|---|---|
| `datos/ordenes/AAAA-MM-DD.json` | la cartera de la semana: par, lado, peso, cierre del lunes y precio límite de cada orden, o si la posición sigue de la semana anterior | el lunes, apenas el bot la decide (00:10 UTC) |
| `datos/cierres/AAAA-MM-DD.json` | qué orden se llenó y a qué hora, a qué precio entró y salió cada posición, la financiación y el resultado | unos minutos después de que empieza la semana siguiente |
| `datos/historial.csv` | una fila por semana cerrada: resultado, acumulado y caída desde el máximo | con cada cierre |
| `index.html`, `app.js`, `estilo.css` | la página en vivo, que pide los precios a Bybit desde el navegador de quien la mira | |
| `verificar.py` | recalcula cada semana cerrada con los precios públicos de Bybit | |

Un archivo publicado no se modifica. El historial de commits de este repositorio deja a la vista cualquier cambio.

## Cómo opera

- **Rebalanceo:** una vez por semana, los lunes. Lo que sigue en la cartera del mismo lado se mantiene; lo que sale
  se cierra.
- **Entrada:** con órdenes límite por debajo del cierre del lunes en las compras (por encima en las ventas en corto),
  más lejos cuanto más se mueve cada moneda. Si en la semana el precio no llega a la orden, se cancela y esa parte de
  la cuenta queda sin usar.
- **Salida:** al lunes siguiente, en el rebalanceo.
- **Tamaño:** 6 compras y 6 ventas en corto, la mitad de la cuenta de cada lado. Sin apalancamiento, cada posición es
  el 8,3 % de la cuenta.
- **Sin stop loss ni take profit**, y sin una relación riesgo/beneficio fija. El riesgo se controla con el tamaño de
  cada posición y con las dos patas compensándose entre sí. Se probó con stops de 5 a 30 % por posición y el backtest
  rinde mucho menos (con 10 %, pasa de +19,9 % a −18,4 % por año): dentro de la semana el precio se mueve lo suficiente
  para hacer saltar el stop en posiciones que el lunes cierran a favor.

## Cómo se comprueba

1. Cada semana empieza a contar dos minutos después de que su archivo de órdenes llega a GitHub (`inicio_utc`). Lo
   que pasó antes no cuenta, así que todo lo que entra en el resultado ocurrió con las órdenes ya publicadas. GitHub
   registra la hora en que recibe cada subida, y la página la muestra para la semana en curso.
2. El resultado sale solo de esos archivos y de los precios públicos de Bybit. Para recalcular todas las semanas
   cerradas y compararlas con lo publicado:

   ```
   python verificar.py
   ```

   Usa solo la biblioteca estándar de Python y no pide cuenta ni claves. En la página, el botón «recalcular» de cada
   semana hace la misma cuenta en el navegador.
### Reglas de la cuenta pública

- Cada semana tiene un archivo en `datos/ordenes/` y empieza a contar en su `inicio_utc`, dos minutos después de
  publicado.
- Una orden de compra se llena en el primer minuto cuyo mínimo llega al precio límite; una venta en corto, en el primer
  minuto cuyo máximo llega. Se llena al precio límite. Puede llenarse hasta el `corte_utc` de la semana siguiente, que
  es el minuto en que se publica la cartera nueva; si no llega, se cancela.
- Una posición marcada `sigue` ya estaba abierta: entra al precio de apertura del minuto `inicio_utc`, sin comisión.
- Todas las posiciones se valúan al precio de apertura del minuto `inicio_utc` de la semana siguiente. Las que no siguen
  se cierran ahí.
- Comisión de 0,10 % del tamaño al entrar y al salir, y la financiación real de cada contrato en cada cobro que ocurre
  con la posición abierta.
- `peso` es la parte de la cuenta que lleva cada posición al empezar la semana. Resultado de una posición: peso ×
  variación del precio (con el signo del lado) − comisiones − financiación pagada.

## Riesgo y apalancamiento

| cuenta | cada posición | las 12 suman | peor semana del backtest | peor caída |
|---|---|---|---|---|
| sin apalancar (la del bot) | 8,3 % | 100 % del saldo | −14,0 % | −45,2 % |
| 1,5x | 12,5 % | 150 % | −21,0 % | −61,5 % |
| 2x | 16,7 % | 200 % | −28,1 % | −74,1 % |

- **El apalancamiento es la suma de las posiciones contra el saldo.** La palanca que Bybit deja elegir en cada contrato
  solo define cuánto margen se reserva: una posición de US$ 417 es la misma apuesta con la palanca en 1x o en 10x.
- **Margen cruzado.** Es el modo por defecto de la cuenta unificada de Bybit, y el bot no lo cambia. Todo el saldo
  respalda todas las posiciones, así que la cuenta se liquida recién cuando el saldo cae hasta el margen de
  mantenimiento (alrededor de 1 % del tamaño total). Con compras y ventas en corto por el mismo monto, eso pide perder
  casi todo el saldo dentro de una misma semana; la peor fue −14,0 % sin apalancar y −28,1 % a 2x. Una sola posición
  sin apalancar tendría que moverse más de 1.000 % en contra en una semana para vaciar la cuenta; la peor del backtest
  fue una venta en corto en BONK que subió 128 % y le costó a la cuenta 10,7 %.
- **En margen aislado** cada posición tiene su propio margen y se liquida sola: a 2x, una moneda que se mueve alrededor
  de 50 % en contra en la semana. El backtest supone margen cruzado.
- **Tamaño semanal.** Cada lunes las posiciones se recalculan sobre el saldo de ese momento; después de una mala racha,
  el bot opera más chico.
- **Mercado.** La correlación semanal con Bitcoin fue +0,04 y con el S&P 500, −0,10.

## Backtest

Bybit, 16 de agosto de 2021 a 31 de agosto de 2026, con comisiones de 0,10 % por operación y la financiación real de
cada contrato. Arranca en agosto de 2021 porque antes Bybit no tenía suficientes monedas para armar la cartera. El
backtest supone entrada a precio de mercado; la entrada con órdenes límite rindió algo más en las pruebas, pero la
diferencia no es concluyente, así que se muestra la versión más conservadora.

| cuenta | US$ 5.000 terminan en | por año | peor caída |
|---|---|---|---|
| 1x (sin apalancar) | US$ 12.473 | +19,9 % | −45,2 % |
| 1,5x | US$ 16.090 | +26,1 % | −61,5 % |
| 2x | US$ 18.143 | +29,1 % | −74,1 % |
| S&P 500 con dividendos (SPY) | US$ 9.230 | +12,9 % | −24,5 % |

Con aportes de US$ 250 por mes además de los US$ 5.000 iniciales (US$ 20.000 invertidos en total): 1x US$ 51.944,
1,5x US$ 74.535, 2x US$ 98.683, S&P 500 US$ 33.094.

- Las tres cuentas estuvieron por debajo de lo invertido desde agosto de 2021 hasta diciembre de 2023. Las apalancadas
  volvieron a quedar debajo más tarde: la de 1,5x por última vez en octubre de 2024 y la de 2x en febrero de 2026.
- Por encima de 2x deja de convenir: las caídas superan el 80 % y el rendimiento anual baja.
- El costo real de operar, medido con cada operación ejecutada en Bybit durante 234 lunes, dio alrededor de 0,07 %
  por operación, menos que el 0,10 % que se usa en el backtest.

Un backtest no dice cómo le va a ir al bot de acá en adelante. Para eso está el registro en vivo.

*No es una recomendación de inversión.*
