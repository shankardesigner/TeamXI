import { useEffect, useMemo, useState } from "react";
import { fetchMatchPrediction, fetchTeams, fetchVenues } from "../api/xi.js";

const MATCH_TYPES = ["T20", "ODI"];
