from pathlib import Path
from fractions import Fraction as Q
import json
h=Path(__file__).resolve().parent
rows={c["id"]:json.loads(c["expected_wire"]) for c in json.loads((h/"source-vectors.json").read_text())["cases"]}
checks=[]
def check(id,field,want):
 got=Q(rows[id]["result"]["value"][field]);assert got==want,(id,field,str(got),str(want));checks.append({"id":id,"field":field,"exact":str(want)})
for id in ["caller-factor","caller-symbol-alias","caller-referenced-id","caller-last-wins"]:check(id,"canonical_magnitude",Q(2)*50)
check("caller-rational-factor","canonical_magnitude",Q(2,3))
check("caller-add","canonical_magnitude",Q(2)*50+3)
check("caller-add","magnitude",(Q(2)*50+3)/50)
check("caller-subtract","canonical_magnitude",Q(2)*50-3)
check("caller-compound","canonical_magnitude",Q(2)*50*3)
check("caller-ratio","canonical_magnitude",Q(2)*50/4)
check("registered-affine-point","canonical_magnitude",Q(20)+Q("273.15"))
check("registered-affine-difference","canonical_magnitude",Q(20))
check("registered-affine-subtraction","canonical_magnitude",Q(20)-15)
check("canonical-tolerance-exact","canonical_magnitude",Q(2)*Q("1.00000000005"))
check("register-empty","canonical_magnitude",Q(2))
check("caller-target-only","canonical_magnitude",Q(100))
check("caller-compound-target","canonical_magnitude",Q(100))
for id in ["caller-target-only","caller-compound-target"]:
 got=Q(rows[id]["result"]["converted"]["magnitude"]);assert got==Q(100)/50
 checks.append({"id":id,"field":"converted.magnitude","exact":"2"})
assert rows["registered-affine-subtraction"]["result"]["value"]["scale"]=="difference"
assert rows["registered-affine-point"]["result"]["value"]["scale"]=="interval"
assert rows["register-does-not-persist"]["error"]["code"]=="MissingUnitConversionError"
output={"passed":True,"exact_arithmetic_checks":checks,"count":len(checks),"tolerance":"none; Fraction equality", "conventions":["Factor50 and1/3 are explicit caller registrations from the published helper source vectors; no normative SI factor for cwt(US) is inferred.","Interval+interval addition retains existing aligned-display source behavior, without asserting a new physical affine-addition rule."]}
(h/"reference-check.json").write_text(json.dumps(output,indent=2)+"\n");print(json.dumps({"exact_checks":len(checks),"passed":True}))
