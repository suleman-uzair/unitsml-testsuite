require "json"
require "digest"
require "plurimath"
def wire(v)
 case v
 when Hash then v.transform_values { |x| wire(x) }
 when Array then v.map { |x| wire(x) }
 when Rational then {rational:[v.numerator.to_s,v.denominator.to_s]}
 when BigDecimal then {decimal:v.to_s("F")}
 when Symbol then {symbol:v.to_s}
 else v end
end
G=Plurimath::Math::Evaluation::Gum
CASES=[]
def record(id,method,args)
 result=yield
 CASES << {id:id,request:{schema:"plurimath.evaluate.gum/1",method:method,parameters:wire(args)},expected:{outcome:"ok",result:wire(result)}}
 result
rescue G::InvalidInput => e
 CASES << {id:id,request:{schema:"plurimath.evaluate.gum/1",method:method,parameters:wire(args)},expected:{outcome:"error",error_class:e.class.name,message:e.message}}
end
data=JSON.parse(File.read(ARGV.fetch(0))).fetch("h3")
base={temperatures:data.fetch("temperatures_C"),corrections:data.fetch("corrections_C"),reference_temperature:"20",abscissa_uncertainty: :negligible,residual_model: :independent_common_variance,guard_digits:40}
fits=["20","24.0085"].map do |t|
 args=base.merge(reference_temperature:t)
 record("h3-fit-#{t}","linear_calibration",args){G.linear_calibration(**args)}
end
fits.each_with_index do |fit,i|
 [:mean_correction,:new_observation].each do |target|
  args={calibration:fit,temperature:30,target:target,temperature_uncertainty: :negligible,guard_digits:40}
  record("h3-predict-#{i}-#{target}","predict_calibration",args){G.predict_calibration(fit,**args.reject{|k,_|k==:calibration})}
 end
 args={covariance:fit[:covariance],guard_digits:40}
 record("h3-correlation-#{i}","correlation_matrix",args){G.correlation_matrix(args[:covariance],guard_digits:40)}
end
[base.merge(temperatures:[1,1,1],corrections:[1,2,3]),base.merge(abscissa_uncertainty: :significant)].each_with_index{|args,i|record("h3-refusal-#{i}","linear_calibration",args){G.linear_calibration(**args)}}
base={estimates:[0,0],output_jacobian:[[0,1],[1,0]],input_jacobian:[[1],[2]],covariance:[[3]],residuals:[0,0],residual_tolerance:0,guard_digits:40}
[base,base.merge(output_jacobian:[[1,1],[1,1]]),base.merge(residuals:[1,0])].each_with_index{|args,i|record("implicit-pivot-#{i}","propagate_implicit",args){G.propagate_implicit(**args)}}

data=JSON.parse(File.read(ARGV.fetch(1))).fetch("thermometer")
    r0, a, b, rs = %w[R0 A B RS].map { |key| Rational(data.fetch(key)) }
    ratios = data.fetch("W").map { |value| Rational(value) }
    roots = Plurimath::Math::Evaluation::Accuracy.with_decimal_context do
      BigDecimal.limit(90)
      ratios.map do |w|
        t = BigDecimal("20")
        12.times do
          residual = (1 + a*t + b*t*t)*r0 - w*rs
          break if residual.abs < BigDecimal("1e-75")
          t -= residual.div((a + 2*b*t)*r0, 85)
        end
        t.to_r
      end
    end
    size = 4 + ratios.length
    u = data.fetch("standard_uncertainties").map { |value| Rational(value) }
    cov = Array.new(size) { |i| Array.new(size) { |j| i == j ? u[i < 4 ? i : 4]**2 : 0r } }
    3.times { |i| 3.times { |j| cov[i][j] = u[i]*u[j]*Rational(data.fetch("parameter_correlations")[i][j]) } }
    cy = roots.each_index.map { |i| roots.each_index.map { |j| i == j ? (a + 2*b*roots[i])*r0 : 0r } }
    cx = roots.each_with_index.map do |t, i|
      [1+a*t+b*t*t, r0*t, r0*t*t, -ratios[i]] + ratios.each_index.map { |j| i == j ? -rs : 0r }
    end
    residuals = roots.each_with_index.map { |t, i| (1+a*t+b*t*t)*r0-ratios[i]*rs }
args={estimates:roots,output_jacobian:cy,input_jacobian:cx,covariance:cov,residuals:residuals,residual_tolerance:"1e-70",guard_digits:65}
record("implicit-ten-temperature","propagate_implicit",args){G.propagate_implicit(**args)}

h=JSON.parse(File.read(ARGV.fetch(0))).fetch("h6")
    d,sd,resolution,standard,calibration,fractional,national = %w[mean_depth_scale_units pooled_sd_scale_units resolution_scale_units standard_average_sd_scale_units calibration_average_sd_scale_units fractional_variation national_definition_u_scale_units].map { |key| Rational(h.fetch(key)) }
    resolution_component = G.component(distribution: :rectangular,half_width:resolution/2)
    transfer_component = G.component(distribution: :triangular,half_width:fractional*d/2)
    parts = [{variance:sd**2/5+resolution_component[:variance],degrees_of_freedom: :unknown},
             {variance:standard**2/h.fetch("standard_series_count")+calibration**2/h.fetch("calibration_series_count"),degrees_of_freedom: :unknown},
             transfer_component,{variance:national**2,degrees_of_freedom: :unknown}]
def node(v);{type:"variable",name:v};end
ast=%w[d c b s].reduce({type:"number",text:"100"}){|left,name|{type:"binary",operator:"-",left:left,right:node(name)}}
args={ast:ast,inputs:%w[d c b s].zip([d,0,0,0],parts).map{|name,estimate,component|{name:name,estimate:estimate,component:component}},independent:true,guard_digits:50}
record("h6-resolution-and-unknown-dof","analyze",args){G.analyze(Plurimath::Math.parse("100-d-c-b-s",:asciimath),estimates:{d:d,c:0,b:0,s:0},components:%i[d c b s].zip(parts).to_h,independent:true,guard_digits:50)}
args={estimates:[1,0],output_jacobian:[[1,0],[0,1]],input_jacobian:[[-1],[0]],covariance:[[1]],residuals:[0,0],residual_tolerance:0,guard_digits:40}
record("implicit-exact-unit-and-zero","propagate_implicit",args){G.propagate_implicit(**args)}
args={covariance:[[0,0,0],[0,1,-1],[0,-1,1]],guard_digits:40}
record("correlations-zero-and-negative-perfect","correlation_matrix",args){G.correlation_matrix(args[:covariance],guard_digits:40)}
puts JSON.generate({ruby:RUBY_DESCRIPTION,cases:CASES})
