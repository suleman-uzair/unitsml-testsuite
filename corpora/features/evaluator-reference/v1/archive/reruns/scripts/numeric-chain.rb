require "json"
require "plurimath"
require ARGV.fetch(0)
class WireAst < Plurimath::Math::Evaluation::Evaluator
 def number_value(raw); {type:"number",text:raw.to_s};end
 def real_result(value);value;end
 def normalize_bindings(bindings);bindings.transform_keys(&:to_s);end
 def value_for(name)
  return bindings.fetch(name) if bindings.fetch(name).is_a?(Hash)
  q=bindings.fetch(name).to_r
  q.denominator==1 ? number_value(q.numerator) : divide(number_value(q.numerator),number_value(q.denominator))
 end
 def binary(op,a,b);{type:"binary",operator:op,left:a,right:b};end
 def add(a,b);binary("+",a,b);end
 def subtract(a,b);binary("-",a,b);end
 def multiply(a,b,implicit:);binary("*",a,b);end
 def divide(a,b);binary("/",a,b);end
 def power(a,b);binary("^",a,b);end
 def positive(a);{type:"unary",operator:"+",operand:a};end
 def negate(a);{type:"unary",operator:"-",operand:a};end
 def group(a);{type:"group",expression:a};end
 def limited_operation(label,values);raise "arity" unless values.length==1;{type:"call",name:label=="log" ? "ln" : label,argument:values.first};end
 def square_root(node);limited_operation("sqrt",[evaluate_node(node)]);end
end
CASES=[]
def numeric(source,bindings)
 formula=Plurimath::Math.parse(source,:asciimath)
 ast=WireAst.new(formula,bindings,mode: :strict,guard_digits:60).evaluate_formula(formula)
 request={schema:"plurimath.evaluate.numeric/1",ast:ast,mode:"strict",guard_digits:60}
 result=Plurimath::EvaluationRequest.call(JSON.generate(request))
 CASES << {id:"annex-numeric-#{CASES.length+1}",source:source,request:request,expected_wire:result}
 # Keep the source evaluator's exact values for the published downstream covariance fixtures.
 actual=formula.evaluate(bindings,mode: :strict,guard_digits:60).value
 value=JSON.parse(result).fetch("result").fetch("value")
 decoded=case value.fetch("kind")
 when "integer" then Rational(value.fetch("value"))
 when "rational" then Rational(value.fetch("numerator"),value.fetch("denominator"))
 when "decimal" then Rational(value.fetch("value"))
 else raise "unexpected value #{value}" end
 raise "AST substitution changed #{source}" unless decoded==actual.to_r
 actual
end
G=Plurimath::Math::Evaluation::Gum
GUM_CASES=[]
def wire(v)
 case v
 when Hash then v.transform_values{|x|wire(x)}
 when Array then v.map{|x|wire(x)}
 when Rational then {rational:[v.numerator.to_s,v.denominator.to_s]}
 when BigDecimal then {decimal:v.to_s("F")}
 when Symbol then {symbol:v.to_s}
 else v end
end
def gum_record(id,method,params)
 result=yield
 GUM_CASES << {id:id,request:{schema:"plurimath.evaluate.gum/1",method:method,parameters:wire(params)},expected:{outcome:"ok",result:wire(result)}}
 result
end
inputs=JSON.parse(File.read(ARGV.fetch(1)))
paired=G.type_a_covariance(inputs.fetch("h2").fetch("observations"));v,i,p=paired[:means];bindings={v:v,i:i,p:p}
expressions=["1000*v/i*cos(p)","1000*v/i*sin(p)","1000*v/i"]
estimates=expressions.map{|s|numeric(s,bindings)}
gradient_sources=[["1000*cos(p)/i","-1000*v*cos(p)/i^2","-1000*v*sin(p)/i"],["1000*sin(p)/i","-1000*v*sin(p)/i^2","1000*v*cos(p)/i"],["1000/i","-1000*v/i^2","0"]].map{|row|row.map{|s|numeric(s,bindings)}}
args={estimates:estimates,jacobian:gradient_sources,covariance:paired[:covariance_of_mean],guard_digits:50}
output=gum_record("h2-derived-vector","propagate_vector",args){G.propagate_vector(**args)}
gum_record("h2-correlations","correlation_matrix",{covariance:output[:covariance],guard_digits:50}){G.correlation_matrix(output[:covariance],guard_digits:50)}
rows=inputs.fetch("h2").fetch("observations").map{|row|expressions.map{|s|numeric(s,%i[v i p].zip(row.map{|v|Rational(v)}).to_h)}}
gum_record("h2-derived-observations","type_a_covariance",{observations:rows}){G.type_a_covariance(rows)}
h=inputs.fetch("h4")
rates=h.fetch("observations").map do |row|
 ts,cs,tb,cb,tx,cx=row.map{|v|Rational(v)};common={b:cb,t:Rational(h.fetch("counting_time_min")),l:Rational(h.fetch("decay_constant_per_min"))}
 [numeric("(c-b)/t*exp(l*x)",common.merge(c:cx,x:tx)),numeric("(c-b)/t*exp(l*x)",common.merge(c:cs,x:ts))]
end
paired=G.type_a_covariance(rates);a,m,n=%w[standard_activity_Bq_per_g standard_mass_g sample_mass_g].map{|k|Rational(h.fetch(k))};x,s=paired[:means];bindings={a:a,m:m,n:n,x:x,s:s}
derived=["a*m/n*x/s","m/n*x/s","a/n*x/s","-a*m/n^2*x/s","a*m/(n*s)","-a*m/n*x/s^2"].map{|s|numeric(s,bindings)}
au,mu,nu=%w[standard_activity_u standard_mass_u sample_mass_u].map{|k|Rational(h.fetch(k))}
variances=[au**2,mu**2,nu**2,paired[:covariance_of_mean][0][0],paired[:covariance_of_mean][1][1]]
covariance=Array.new(5){|j|Array.new(5){|k|j==k ? variances[j] : 0}}
covariance[3][4]=covariance[4][3]=paired[:covariance_of_mean][0][1]
args={estimate:derived.first,components:variances.map{|v|{variance:v}},gradient:derived.drop(1),covariance:covariance,joint_distribution: :unspecified,guard_digits:50}
gum_record("h4-derived-covariance","propagate_covariance",args){G.propagate_covariance(**args)}
ratios=G.type_a(rates.map{|rx,rs|rx/rs});parameters={a:a,m:m,n:n,r:ratios[:mean]}
components={a:{variance:au**2,degrees_of_freedom: :unknown},m:{variance:mu**2,degrees_of_freedom: :unknown},n:{variance:nu**2,degrees_of_freedom: :unknown},r:ratios}
formula=Plurimath::Math.parse("a*m/n*r",:asciimath)
ast=WireAst.new(formula,parameters.transform_values.with_index{|_,i|{type:"variable",name:parameters.keys[i].to_s}},mode: :strict).evaluate_formula(formula)
args={ast:ast,inputs:parameters.map{|name,estimate|{name:name.to_s,estimate:estimate,component:components.fetch(name)}},independent:true,guard_digits:50}
gum_record("h4-ratio-approach","analyze",args){G.analyze(formula,estimates:parameters,components:components,independent:true,guard_digits:50)}
puts JSON.generate({ruby:RUBY_DESCRIPTION,cases:CASES,gum_cases:GUM_CASES})
