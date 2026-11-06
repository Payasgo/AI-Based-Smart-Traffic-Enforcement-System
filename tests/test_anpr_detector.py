from detectors.anpr_detector import PlateRecognition


def test_plate_normalization_removes_spaces_and_punctuation():
    assert PlateRecognition.normalize(" ts 09 - ab 1234 ") == "TS09AB1234"


def test_consensus_requires_multiple_matching_observations():
    recognizer = PlateRecognition(history_size=5, min_votes=3)
    history = recognizer._votes["track-1"]
    history.extend(["TS09AB1234", "TS09AB1234"])
    assert history.count("TS09AB1234") == 2
    history.append("TS09AB1234")
    assert history.count("TS09AB1234") == 3
