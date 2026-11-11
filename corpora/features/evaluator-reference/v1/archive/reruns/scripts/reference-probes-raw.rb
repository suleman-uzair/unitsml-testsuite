# Same as plurimath-rs scripts/reference-probes.rb, but a row may carry the raw
# request text as "request_json" (malformed-input cases) instead of "request".
require "json"
require ARGV.fetch(0)
rows = JSON.parse(File.read(ARGV.fetch(1)))
rows.fetch("cases").each do |row|
  raw = row.key?("request_json") ? row.fetch("request_json") : JSON.generate(row.fetch("request"))
  row["expected_wire"] = Plurimath::EvaluationRequest.call(raw)
end
File.write(ARGV.fetch(2), JSON.pretty_generate(rows) + "\n")
puts JSON.generate({"executed" => rows.fetch("cases").length})
