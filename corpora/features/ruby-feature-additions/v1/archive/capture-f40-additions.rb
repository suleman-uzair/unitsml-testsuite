# F40 claude-20261111 additive producer: two families the coverage matrix found missing
# and the existing Ruby APIs can produce. Values are recorded exactly as Ruby returns
# them, with the same wire encoding as handoffs/F40/capture-ruby-features.rb.
#   accuracy_classes  (WORK-PACKAGES F04:70 "all accuracy modes"; #543 exact/limited classes)
#   unit_text_roundtrip (WORK-PACKAGES F02:42 "exact string ... roundtrips"; strings are the
#                        literal expectations of unitsml-ruby spec/unitsml/composite_spec.rb)
require "json"
require "bigdecimal"
require "plurimath"
require "unitsml"

def wire(value)
  case value
  when nil, true, false, String, Integer then value
  when Symbol then { "symbol" => value.to_s }
  when Rational then { "rational" => [value.numerator.to_s, value.denominator.to_s] }
  when BigDecimal then { "decimal" => value.to_s("F") }
  when Float then { "binary64" => [value].pack("G").unpack1("H*") }
  when Array then value.map { |item| wire(item) }
  when Hash then value.to_h { |key, item| [key.to_s, wire(item)] }
  else raise TypeError, "Unserialized value: #{value.class}"
  end
end

ROWS = []
def q(value, unit) = Unitsml::Quantity.new(value: value, unit: unit)

def accuracy(id, formula, bindings)
  out = Plurimath::Math.parse(formula, :asciimath).evaluate_quantity(bindings)
  ROWS << { family: "accuracy_classes", id: id, formula: formula,
            inputs: bindings.transform_values { |b| { value: b.value, unit: b.norm_text } },
            outcome: "ok", value: out.value.value, unit: out.value.norm_text, accuracy: out.accuracy }
rescue StandardError => e
  ROWS << { family: "accuracy_classes", id: id, formula: formula, outcome: "error",
            error_class: e.class.name, message: e.message }
end

accuracy("exact-rational", "x*y", { x: q(Rational(5, 2), "m"), y: q(3, "s") })
accuracy("limited-float", "x*y", { x: q(2.5, "m"), y: q(3, "s") })
accuracy("limited-decimal", "x*y", { x: q(BigDecimal("2.50"), "m"), y: q(3, "s") })
accuracy("least-precise-wins-decimal", "x*y", { x: q(BigDecimal("2.50"), "m"), y: q(BigDecimal("3.1"), "s") })
accuracy("least-precise-wins-float", "x*y", { x: q(BigDecimal("2.50"), "m"), y: q(3.0, "s") })
accuracy("limited-sum-same-unit", "x+y", { x: q(BigDecimal("1.5"), "m"), y: q(2, "m") })

def roundtrip(text)
  first = Unitsml.parse(text)
  norm = first.norm_text
  again = Unitsml.parse(norm).norm_text
  ROWS << { family: "unit_text_roundtrip", id: "roundtrip-#{text}", input: text, norm_text: norm,
            reparsed_norm_text: again, idempotent: norm == again, outcome: "ok" }
rescue StandardError => e
  ROWS << { family: "unit_text_roundtrip", id: "roundtrip-#{text}", input: text, outcome: "error",
            error_class: e.class.name, message: e.message }
end

["W/m", "m/s", "km/s", "W*m^(-1)*sr^(-1)", "J*s^(-1)*m^(-1)*s", "W*m^(-1)*s", "W*m^(-1)"].each { |t| roundtrip(t) }

ROWS.each { |row| puts JSON.generate(wire(row)) }
