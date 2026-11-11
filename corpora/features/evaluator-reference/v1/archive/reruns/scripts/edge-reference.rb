require "json"
require "plurimath/math/evaluation/gum"
require "plurimath/math/evaluation/statistics"
require "plurimath/math/evaluation/conformity"

def wire(value)
  case value
  when Hash then value.transform_values { |child| wire(child) }
  when Array then value.map { |child| wire(child) }
  when Symbol then { symbol: value.to_s }
  else value
  end
end

base = {estimate: 0, standard_uncertainty: 1, distribution: :normal, knowledge: :measurement_only,
        tolerance: [-2, 2], rule: :three_zone, coverage_factor: 1, guard_ratio: 1, guard_digits: 12}
cases = [
  ["simple-upper-limit", {estimate: 2, rule: :simple, guard_ratio: 0}],
  ["guarded-acceptance-inner-upper", {estimate: 1, rule: :guarded_acceptance}],
  ["guarded-acceptance-outside-inner", {estimate: "1.000000000001", rule: :guarded_acceptance}],
  ["three-zone-inner-upper", {estimate: 1}],
  ["three-zone-past-inner-upper", {estimate: "1.000000000001"}],
  ["three-zone-outer-lower", {estimate: -3}],
  ["three-zone-past-outer-lower", {estimate: "-3.000000000001"}],
  ["three-zone-one-sided-open-lower", {estimate: 3, tolerance: [nil, 2]}],
]
puts JSON.generate({ruby: RUBY_VERSION, cases: cases.map do |id, changes|
  params = base.merge(changes)
  result = Plurimath::Math::Evaluation::Gum.conformity(**params)
  {id: id, request: {schema: "plurimath.evaluate.gum/1", method: "conformity", parameters: wire(params)},
   expected: {outcome: "ok", result: wire(result)}}
end})
