# Ruby reference for the 3 frozen quantity wires (same API as handoffs/F40/capture-ruby-quantity.rb).
require "json"
require "plurimath"
require "unitsml"
def run(id, v, i, target)
  b = { v: Unitsml::Quantity.new(value: v[0], unit: v[1]), i: Unitsml::Quantity.new(value: i[0], unit: i[1]) }
  out = Plurimath::Math.parse("v*i", :asciimath).evaluate_quantity(b)
  q = out.value; c = q.convert_to(target)
  { id: id, ok: true, magnitude: q.value.to_s, unit: q.norm_text, dimensions: q.dimension_vector, accuracy: out.accuracy.to_s,
    converted: { magnitude: c.value.to_r.to_s, unit: c.norm_text } }
rescue StandardError => e
  { id: id, ok: false, error_class: e.class.name, message: e.message[0, 300] }
end
rows = [run("refusals-14", [2, "kV"], [3, "A"], "kW"),
        run("volts-amperes-to-kilowatts", [2000, "V"], [3, "A"], "kW"),
        run("pinned-asciiunits-syntax-offset", [2000, "m^^2"], [3, "A"], "kW")]
puts JSON.pretty_generate(rows)
