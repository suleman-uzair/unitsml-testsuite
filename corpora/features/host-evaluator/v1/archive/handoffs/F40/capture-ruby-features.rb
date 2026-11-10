require "json"
require "digest"
require "rspec"
require "plurimath"
require "unitsml"

module FeatureCapture
  OUT = ENV.fetch("F40_OUTPUT")
  METHODS = {
    Plurimath::Math::Evaluation::Gum => %i[type_a_covariance propagate_vector type_a grouped_type_a series conformity validate_coverage component propagate_covariance coverage decimal_output decimal_places_output],
    Plurimath::Math::Evaluation::Statistics => %i[quantile cdf],
  }.freeze

  def self.wire(value)
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

  def self.emit(row)
    File.open(OUT, "a") { |file| file.puts JSON.generate(wire(row)) }
  end

  METHODS.each do |owner, methods|
    layer = Module.new
    methods.select { |name| owner.respond_to?(name) }.each do |name|
      layer.define_method(name) do |*args, **kwargs, &block|
        example = RSpec.current_example
        if !example || Thread.current[:f40_capture]
          super(*args, **kwargs, &block)
        else
          Thread.current[:f40_capture] = true
          source = { example: example.full_description, spec: example.metadata.fetch(:file_path), line: example.metadata.fetch(:line_number) }
          begin
            begin
              value = super(*args, **kwargs, &block)
            rescue StandardError => error
              FeatureCapture.emit(source.merge(method: name, args: args, kwargs: kwargs, error: { type: error.class.name, message: error.message }))
              raise
            end
            FeatureCapture.emit(source.merge(method: name, args: args, kwargs: kwargs, result: value))
            value
          ensure
            Thread.current[:f40_capture] = false
          end
        end
      end
    end
    owner.singleton_class.prepend(layer)
  end
end
