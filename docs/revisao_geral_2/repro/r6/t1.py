from src.services.trf_import import build_trf_rounds
P=lambda r,c:{"start_rank":r,"rounds":[c]}
# 1 (brancas) x 2; resultado com letra desconhecida 'X'; 3 enfrenta rank 9 inexistente
players=[P(1,{"opponent_rank":"2","color":"w","result":"X"}),P(2,{"opponent_rank":"1","color":"b","result":"0"}),
         P(3,{"opponent_rank":"9","color":"w","result":"1"}),P(4,{"opponent_rank":"3","color":"b","result":"0"})]
print(build_trf_rounds(players,{1:11,2:12,3:13,4:14}))
