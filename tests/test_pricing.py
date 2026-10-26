import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

nb=json.loads((Path(__file__).resolve().parents[1]/"Capstone (2).ipynb").read_text(encoding="utf-8"))

def model_two(tmp_path, capacity):
    path=tmp_path/"parking.csv"
    pd.DataFrame({"SystemCodeNumber":["A","A"],"LastUpdatedDate":["01-12-2016"]*2,"LastUpdatedTime":["10:00:00","11:00:00"],"Occupancy":[1,1],"Capacity":[capacity]*2,"QueueLength":[0,0],"TrafficConditionNearby":[0,0],"IsSpecialDay":[0,0],"VehicleType":["car","car"]}).to_csv(path,index=False)
    scope={"pd":pd,"np":np,"uploaded":{str(path):None}}
    code="".join(nb["cells"][3]["source"]).split("# STEP 10:")[0]
    exec(compile(code,"pricing_model_2","exec"),scope)
    return scope["df"]

def test_constant_demand_stays_finite(tmp_path):
    result=model_two(tmp_path,10)
    assert result["price"].tolist()==[10.,10.]

def test_nonpositive_capacity_rejected(tmp_path):
    with pytest.raises(ValueError,match="Capacity"): model_two(tmp_path,0)
