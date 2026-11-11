require "json"
require "digest"
require "plurimath"
Dir.chdir(ENV.fetch("REFERENCE_CWD", Dir.pwd))
G=Plurimath::Math::Evaluation::Gum
M=Plurimath::Math::Evaluation::MonteCarlo
ROWS=[]
def wire(value)
 case value
 when Hash then value.transform_values{|v|wire(v)}
 when Array then value.map{|v|wire(v)}
 when Rational then {rational:[value.numerator.to_s,value.denominator.to_s]}
 when BigDecimal then {decimal:value.to_s("F")}
 when Symbol then {symbol:value.to_s}
 else value end
end
def capture(id,args,kind="metadata-boundary")
 result=G.validate_coverage(**args)
 ROWS << {id:id,kind:kind,request:{schema:"plurimath.evaluate.gum/1",method:"validate_coverage",parameters:wire(args)},expected:{outcome:"ok",result:wire(result)}}
rescue StandardError => error
 ROWS << {id:id,kind:kind,request:{schema:"plurimath.evaluate.gum/1",method:"validate_coverage",parameters:wire(args)},expected:{outcome:"error",error_class:error.class.name,message:error.message}}
end
formula=Plurimath::Math.parse("x",:asciimath)
settings={inputs:{x:{distribution: :normal,location:3,sd:2}},independent:true,seeds:[12345,23456,34567,45678],probability:"0.95",interval: :both,significant_digits:2,guard_digits:12,max_samples:200000}
mc=G.monte_carlo(formula,**settings)
mc_request={schema:"plurimath.evaluate.gum/1",method:"monte_carlo",parameters:settings.merge(ast:{type:"variable",name:"x"},inputs:settings[:inputs].map{|name,pdf|{name:name.to_s,pdf:pdf}})}
raise "reference MCM did not stabilize" unless mc[:stabilized]
base={guf_interval:["-0.919927969080108","6.919927969080108"],guf_standard_uncertainty:2,significant_digits:1,probability:"0.95",interval: :symmetric,monte_carlo:mc}
capture("actual-normal-symmetric",base,"actual-source-MCM")
capture("actual-normal-shortest",base.merge(interval: :shortest),"actual-source-MCM")
capture("actual-far-interval",base.merge(guf_interval:[2,4]),"actual-source-MCM")
capture("actual-too-coarse",base.merge(significant_digits:2),"actual-source-MCM")
bounds=mc[:intervals][:symmetric].map{|v|Rational(v)};target=M.numerical_tolerance(2,1).to_r
capture("endpoint-equality-inclusive",base.merge(guf_interval:[bounds[0]-target,bounds[1]+target]))
capture("endpoint-past-boundary",base.merge(guf_interval:[bounds[0]-target-Rational(1,10**20),bounds[1]+target]))
capture("five-times-equality",base.merge(monte_carlo:mc.merge(numerical_tolerance:(target/5).to_s)))
capture("five-times-past-boundary",base.merge(monte_carlo:mc.merge(numerical_tolerance:(target/5+Rational(1,10**20)).to_s)))
[0,-1,"2",1.0,13].each{|v|capture("significant-digits-#{v.inspect}",base.merge(significant_digits:v))}
[0,-1,"invalid",nil].each{|v|capture("uncertainty-#{v.inspect}",base.merge(guf_standard_uncertainty:v))}
[[],[0],[0,1,2],[2,1]].each_with_index{|v,i|capture("GUF-endpoints-#{i}",base.merge(guf_interval:v))}
capture("probability-mismatch",base.merge(probability:"0.9"))
capture("not-stabilized",base.merge(monte_carlo:mc.merge(stabilized:false)))
capture("wrong-MCM-method",base.merge(monte_carlo:mc.merge(method: :fixed_mcm)))
capture("wrong-interval-kind",base.merge(interval: :both))
[:probability,:numerical_tolerance,:intervals].each do |key|
 remaining=mc.reject{|name,_|name==key}
 capture("missing-#{key}",base.merge(monte_carlo:remaining))
end
capture("missing-requested-interval",base.merge(monte_carlo:mc.merge(intervals:{})))
[nil,[],false,"interval-map"].each_with_index{|v,i|capture("malformed-intervals-#{i}",base.merge(monte_carlo:mc.merge(intervals:v)))}
[nil,[],[0],[0,1,2],"bounds"].each_with_index do |value,i|
 changed=mc.merge(intervals:{symmetric:value})
 capture("malformed-bounds-#{i}",base.merge(monte_carlo:changed))
end
# These probes record the trusted-metadata boundary; they do not pretend to be engine results.
capture("metadata-negative-tolerance",base.merge(monte_carlo:mc.merge(numerical_tolerance:"-1")))
capture("metadata-out-of-range-probability",base.merge(probability:2,monte_carlo:mc.merge(probability:2)))
["9.94","9.95","99.49","99.5","0.00995","1e-50","1e400","1e-400"].each_with_index do |u,i|
 meta=mc.merge(numerical_tolerance:"0",intervals:{symmetric:[0,1]})
 capture("exact-tolerance-#{i}",base.merge(guf_interval:[0,1],guf_standard_uncertainty:u,significant_digits:2,monte_carlo:meta))
end
files=[G.method(:validate_coverage).source_location.first,M.method(:numerical_tolerance).source_location.first]
puts JSON.generate({source:{ruby:RUBY_DESCRIPTION,files:files.to_h{|p|[p,Digest::SHA256.file(p).hexdigest]}},actual_monte_carlo:wire(mc),actual_monte_carlo_request:wire(mc_request),cases:ROWS})
