require_relative "capture-ruby-features"
inputs = { v: [2, "kV"], i: [3, "A"] }
bindings = inputs.transform_values { |value, unit| Unitsml::Quantity.new(value: value, unit: unit) }
outcome = Plurimath::Math.parse("v*i", :asciimath).evaluate_quantity(bindings)
quantity = outcome.value
converted = quantity.convert_to("kW")
raise "Unexpected result" unless converted.value == 6
FeatureCapture.emit({ id: "voltage-times-current", formula: "v*i", inputs: inputs,
                     outcome: { magnitude: quantity.value, unit: quantity.norm_text,
                                dimensions: quantity.dimension_vector, accuracy: outcome.accuracy },
                     converted: { magnitude: converted.value, unit: converted.norm_text } })
