# F40 claude-20261111 Ruby-oracle producer for three F02 families the coverage
# matrix found missing or native-only (context/research/WORK-PACKAGES.md:42):
#   quantity_kinds     "allowed work/energy versus forbidden same-dimension kinds":
#                      every ordered pair of UnitsDB quantities of one dimension,
#                      added with Unitsml::Quantity kind: (equivalence_class gating)
#   primary_quantity   "primary output and data-order independence": every unit
#                      with several quantity references, primary selected by the
#                      units-schema primary flag under three reference orders
#   caller_register    "caller registers": the evaluator-reference/v1
#                      quantity_register requests executed through
#                      Unitsml::Conversion.with_register (request inputs only;
#                      native expected wires are never read here)
# Usage: ruby capture-unitsml-features.rb <evaluator-reference/v1/vectors.json>
require "json"
require "unitsml"

def wire(value)
  case value
  when nil, true, false, String, Integer then value
  when Symbol then { "symbol" => value.to_s }
  when Rational then { "rational" => [value.numerator.to_s, value.denominator.to_s] }
  when Array then value.map { |item| wire(item) }
  when Hash then value.to_h { |key, item| [key.to_s, wire(item)] }
  else raise TypeError, "Unserialized value: #{value.class}"
  end
end

ROWS = []
Q = Unitsml::Quantity
def error_row(row, e) = row.merge(outcome: "error", error_class: e.class.name)

# --- quantity_kinds ---------------------------------------------------------
DIM = "NISTd15" # L2MT-2: energy, work, heat, torque, moment of force ...
kinds = Unitsml::Unitsdb.database.quantities.select { |q| q.dimension_reference&.id.to_s == DIM }
kinds = kinds.map { |q| Unitsml::QuantityKind.new(q) }.sort_by(&:id)
kinds.each do |a|
  kinds.each do |b|
    row = { family: "quantity_kinds", id: "kind-#{a.id}+#{b.id}", dimension: DIM,
            left: { kind: a.id, equivalence_class: a.equivalence_class, value: 2, unit: "J" },
            right: { kind: b.id, equivalence_class: b.equivalence_class, value: 3, unit: "J" } }
    sum = Q.new(value: 2, unit: "J", kind: a.id) + Q.new(value: 3, unit: "J", kind: b.id)
    ROWS << row.merge(outcome: "ok", value: sum.value, unit: sum.norm_text, kind: sum.kind.id)
  rescue Unitsml::Errors::BaseError => e
    ROWS << error_row(row, e)
  end
end
[["kind-dimension-mismatch", "Pa", "NISTq18"], ["kind-unknown", "J", "no-such-kind"]].each do |id, unit, kind|
  row = { family: "quantity_kinds", id: id, unit: unit, kind: kind }
  Q.new(value: 1, unit: unit, kind: kind)
  ROWS << row.merge(outcome: "ok")
rescue Unitsml::Errors::BaseError => e
  ROWS << error_row(row, e)
end
row = { family: "quantity_kinds", id: "kind-untyped-operand", left: { kind: "NISTq184", unit: "N*m", value: 1 },
        right: { kind: nil, unit: "J", value: 1 } }
sum = Q.new(value: 1, unit: "N*m", kind: "NISTq184") + Q.new(value: 1, unit: "J")
ROWS << row.merge(outcome: "ok", value: sum.value, unit: sum.norm_text, kind: sum.kind.id)

# --- primary_quantity -------------------------------------------------------
Fake = Struct.new(:quantity_references, :identifiers)
units = Unitsml::Unitsdb.database.units.select { |u| u.quantity_references.to_a.size > 1 }
units.sort_by { |u| u.identifiers.to_a.map(&:id).first.to_s }.each do |u|
  refs = u.quantity_references.to_a
  uid = u.identifiers.to_a.find { |i| i.type == "nist" }&.id || u.identifiers.to_a.first.id
  orders = { "data" => refs, "reversed" => refs.reverse, "rotated" => refs.rotate(1) }
  row = { family: "primary_quantity", id: "primary-#{uid}", unit: uid,
          references: refs.map(&:id).sort }
  picks = orders.transform_values do |order|
    Unitsml::QuantityKind.primary_for(Fake.new(order, u.identifiers)).id
  end
  ROWS << row.merge(outcome: "ok", primary: picks["data"], by_order: picks,
                    order_independent: picks.values.uniq.size == 1,
                    first_reference_is_primary: refs.first.id == picks["data"])
rescue Unitsml::Errors::BaseError => e
  ROWS << error_row(row, e)
end

# --- caller_register ----------------------------------------------------------
def binding_quantity(b)
  Q.new(value: Rational(b["value"]), unit: b["unit"], scale: b["difference"] ? :difference : nil)
end

def evaluate(ast, bindings)
  case ast["type"]
  when "variable" then binding_quantity(bindings.fetch(ast["name"]))
  when "binary"
    l = evaluate(ast["left"], bindings)
    r = evaluate(ast["right"], bindings)
    l.public_send(ast["operator"], r)
  else raise ArgumentError, "unsupported ast #{ast['type']}"
  end
end

source = JSON.parse(File.read(ARGV.fetch(0)))["cases"].select { |c| c["profile"] == "quantity_register" }
source.sort_by { |c| c["id"] }.each do |c|
  req = JSON.parse(c["request_json"])
  row = { family: "caller_register", id: "register-#{c['id']}", source_id: c["id"],
          request: req.reject { |k, _| k == "schema" } }
  run = lambda do
    value = evaluate(req["ast"], req["bindings"])
    out = { outcome: "ok", value: value.value, unit: value.norm_text, scale: value.scale }
    if req["convert_to"]
      conv = value.convert_to(req["convert_to"])
      out.merge!(converted_value: conv.value, converted_unit: conv.norm_text)
    end
    out
  end
  result = if req.key?("register") && !req["register"].nil?
             Unitsml::Conversion.with_register(req["register"]) { run.call }
           elsif req.key?("register")
             Unitsml::Conversion.with_register(nil) { run.call }
           else
             run.call
           end
  ROWS << row.merge(result)
rescue Unitsml::Errors::BaseError, ArgumentError => e
  ROWS << error_row(row, e)
end

ROWS.each { |r| puts JSON.generate(wire(r)) }
