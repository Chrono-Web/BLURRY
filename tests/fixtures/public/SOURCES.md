# Test fixtures: sources and licences

Every file here is in the **public domain** (works of the US federal government) and was
downloaded from Wikimedia Commons on 2026-10-03, as the 1920 px rendition Commons serves.
Face boxes in `annotations.json` were checked by hand on 2026-10-03.

| File | Source | Author | Licence | Notes |
|---|---|---|---|---|
| `iss038_crew.jpg` | [Expedition 38 crew members pose for an in-flight crew portrait - NASA ISS038-E-054970.jpg](https://commons.wikimedia.org/wiki/File:Expedition_38_crew_members_pose_for_an_in-flight_crew_portrait_-_NASA_ISS038-E-054970.jpg) | NASA | Public domain |  |
| `challenger_51l_crew.jpg` | [Challenger flight 51-l crew.jpg](https://commons.wikimedia.org/wiki/File:Challenger_flight_51-l_crew.jpg) | NASA | Public domain |  |
| `sts125_crew.jpg` | [STS-125 crew portrait.jpg](https://commons.wikimedia.org/wiki/File:STS-125_crew_portrait.jpg) | NASA | Public domain |  |
| `cabinet_room_1968.jpg` | [Dean Rusk, Lyndon B. Johnson and Robert McNamara in Cabinet Room meeting February 1968.jpg](https://commons.wikimedia.org/wiki/File:Dean_Rusk,_Lyndon_B._Johnson_and_Robert_McNamara_in_Cabinet_Room_meeting_February_1968.jpg) | Yoichi Okamoto | Public domain |  |
| `air_force_ball.jpg` | [U.S. Airmen and their guests dance during the Air Force Ball at the 28th Bomb Wing at Ellsworth Air Force Base, S.D., Sept 070922-F-SF570-539.jpg](https://commons.wikimedia.org/wiki/File:U.S._Airmen_and_their_guests_dance_during_the_Air_Force_Ball_at_the_28th_Bomb_Wing_at_Ellsworth_Air_Force_Base,_S.D.,_Sept_070922-F-SF570-539.jpg) | Staff Sgt. Michael B. Keller | Public domain |  |
| `marines_crop.jpg` | [U.S. Marines and Indonesian marines pose for a group photo while aboard the USS Rushmore.jpg](https://commons.wikimedia.org/wiki/File:U.S._Marines_and_Indonesian_marines_pose_for_a_group_photo_while_aboard_the_USS_Rushmore.jpg) | Cpl. Danny Gonzalez and Cpl. Danny Gonzalez | Public domain | cropped to x 1240–1920, y 340–720 → `marines_crop.jpg` (many small faces) |
| `dental_squadron.jpg` | [Dental squadron makes Travis smile, trains Airmen 160502-F-OT558-005.jpg](https://commons.wikimedia.org/wiki/File:Dental_squadron_makes_Travis_smile,_trains_Airmen_160502-F-OT558-005.jpg) | Senior Airman Amber Carter | Public domain |  |
| `sts125_gps.heic` | derived from `sts125_crew.jpg` | NASA | Public domain | resized to 900 px, encoded as HEIC with macOS `sips`, then fake GPS, XMP creator, make/model and date added with exiftool to test metadata removal |

Test videos are not stored: the tests build them from these images (`tests/media.py`).

Real media of real people go in `tests/fixtures/private/`, which git ignores.
