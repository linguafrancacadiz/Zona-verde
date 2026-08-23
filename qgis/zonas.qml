<!DOCTYPE qgis>
<qgis version="3.28" styleCategories="Symbology|Labeling">
  <renderer-v2 type="categorizedSymbol" attr="tipo" forceraster="0" symbollevels="0">
    <categories>
      <category value="verde"    symbol="0" label="Zona verde (residentes)" render="true"/>
      <category value="naranja"  symbol="1" label="Zona naranja"            render="true"/>
      <category value="azul"     symbol="2" label="Zona azul"               render="true"/>
      <category value="excluida" symbol="3" label="Excluida (vado/PMR/C+D)" render="true"/>
    </categories>
    <symbols>
      <symbol type="line" name="0" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="34,139,34,255"/><prop k="line_width" v="1.4"/>
        </layer>
      </symbol>
      <symbol type="line" name="1" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="255,140,0,255"/><prop k="line_width" v="1.0"/>
        </layer>
      </symbol>
      <symbol type="line" name="2" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="30,110,220,255"/><prop k="line_width" v="1.0"/>
        </layer>
      </symbol>
      <symbol type="line" name="3" alpha="1">
        <layer class="SimpleLine">
          <prop k="line_color" v="200,30,30,255"/><prop k="line_width" v="2.0"/>
          <prop k="customdash" v="3;2"/><prop k="use_custom_dash" v="1"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings>
      <text-style fieldName="via || ' (' || confianza || ')'" fontSize="8"/>
      <placement placement="2"/>
    </settings>
  </labeling>
</qgis>
