#ifdef WORKBENCH
//! Plans one tunnel network as data: which piece goes where, at what turn. Nothing is placed in the world here, so many
//! layouts can be tried and only the best one built. Every random choice comes from one RandomGenerator seeded with
//! the layout seed, and pieces are always considered in catalog order, so the same seed, settings, catalog and ground
//! give the same network.

class SP_TunnelGenSettings
{
	int m_iSeed = 0;
	int m_iCandidates = 8;

	float m_fTargetLength = 300;
	float m_fMaxReach = 150;
	int m_iMaxRooms = 4;
	float m_fRoomSpacing = 40;
	bool m_bLargeRooms = true;

	float m_fBranchChance = 0.5;
	float m_fSideBranchMin = 15;
	float m_fSideBranchMax = 60;
	float m_fStraightWeight = 3;
	float m_fLongStraightShare = 0.5;
	float m_fTurnWeight = 1.5;
	float m_fUTurnWeight = 0.2;
	float m_fWiggleWeight = 1;
	float m_fHumpWeight = 0.4;
	float m_fWaterTrapWeight = 0.2;
	float m_fHoldBearing = 0.6;

	float m_fStandingWeight = 1;
	float m_fCrouchWeight = 0.6;
	float m_fProneWeight = 0.2;

	float m_fMinCover = 1;
	bool m_bCheckCover = true;
	float m_fEntranceExposure = 2;
	float m_fTargetCover = 3.5;
	float m_fSlopeWeight = 1;
	float m_fUpTurnWeight = 0.4;
	float m_fLadderWeight = 0.15;
	int m_iMaxLevelChanges = 8;

	int m_iExtraEntrances = 1;
	float m_fEntranceSpacing = 70;
	float m_fEntranceTolerance = 1.0;
	bool m_bEntranceStaircase = true;
	bool m_bEntranceHole = true;
	bool m_bEntranceRocky = true;
	bool m_bEntranceHillCrawl = true;

	bool m_bMasksAtDoorways = true;
	bool m_bMasksAtAllJoints = true;
	bool m_bAvoidExisting = true;
	bool m_bAvoidWorld = true;
	bool m_bIgnorePlants = true;
	bool m_bLightBlockers = true;
	float m_fMaxStraightRun = 6;
	int m_iKit = 0;

	//------------------------------------------------------------------------------------------------
	//! Everything that shapes a layout, as key=value; (the seed is kept separately)
	string Write()
	{
		string s = "";
		s += "candidates=" + m_iCandidates + ";length=" + m_fTargetLength + ";reach=" + m_fMaxReach + ";";
		s += "rooms=" + m_iMaxRooms + ";roomSpacing=" + m_fRoomSpacing + ";largeRooms=" + Bs(m_bLargeRooms) + ";";
		s += "branch=" + m_fBranchChance + ";sideMin=" + m_fSideBranchMin + ";sideMax=" + m_fSideBranchMax + ";";
		s += "straight=" + m_fStraightWeight + ";longShare=" + m_fLongStraightShare + ";turn=" + m_fTurnWeight + ";uturn=" + m_fUTurnWeight + ";";
		s += "wiggle=" + m_fWiggleWeight + ";hump=" + m_fHumpWeight + ";water=" + m_fWaterTrapWeight + ";hold=" + m_fHoldBearing + ";";
		s += "standing=" + m_fStandingWeight + ";crouch=" + m_fCrouchWeight + ";prone=" + m_fProneWeight + ";";
		s += "minCover=" + m_fMinCover + ";checkCover=" + Bs(m_bCheckCover) + ";exposure=" + m_fEntranceExposure + ";";
		s += "targetCover=" + m_fTargetCover + ";slope=" + m_fSlopeWeight + ";";
		s += "upturn=" + m_fUpTurnWeight + ";ladder=" + m_fLadderWeight + ";maxLevels=" + m_iMaxLevelChanges + ";";
		s += "entrances=" + m_iExtraEntrances + ";entranceSpacing=" + m_fEntranceSpacing + ";entranceTol=" + m_fEntranceTolerance + ";";
		s += "eStair=" + Bs(m_bEntranceStaircase) + ";eHole=" + Bs(m_bEntranceHole) + ";";
		s += "eRocky=" + Bs(m_bEntranceRocky) + ";eHill=" + Bs(m_bEntranceHillCrawl) + ";";
		// (a long chain of + is "too complex" for the compiler: a few short ones)
		s += "masksDoor=" + Bs(m_bMasksAtDoorways) + ";masksAll=" + Bs(m_bMasksAtAllJoints) + ";";
		s += "avoid=" + Bs(m_bAvoidExisting) + ";avoidWorld=" + Bs(m_bAvoidWorld) + ";ignorePlants=" + Bs(m_bIgnorePlants) + ";";
		s += "blockers=" + Bs(m_bLightBlockers) + ";maxRun=" + m_fMaxStraightRun + ";kit=" + m_iKit + ";";
		return s;
	}

	//------------------------------------------------------------------------------------------------
	protected string Bs(bool value)
	{
		if (value)
			return "1";

		return "0";
	}

	//------------------------------------------------------------------------------------------------
	protected bool B(string value)
	{
		value.ToLower();
		return value == "1" || value == "true";
	}

	//------------------------------------------------------------------------------------------------
	void Read(string text)
	{
		array<string> pairs = {};
		text.Split(";", pairs, true);
		foreach (string pair : pairs)
		{
			int eq = pair.IndexOf("=");
			if (eq <= 0)
				continue;

			string key = pair.Substring(0, eq);
			string v = pair.Substring(eq + 1, pair.Length() - eq - 1);
			float f = v.ToFloat();
			int i = v.ToInt();
			switch (key)
			{
				case "candidates": m_iCandidates = i; break;
				case "length": m_fTargetLength = f; break;
				case "reach": m_fMaxReach = f; break;
				case "rooms": m_iMaxRooms = i; break;
				case "roomSpacing": m_fRoomSpacing = f; break;
				case "largeRooms": m_bLargeRooms = B(v); break;
				case "branch": m_fBranchChance = f; break;
				case "sideMin": m_fSideBranchMin = f; break;
				case "sideMax": m_fSideBranchMax = f; break;
				case "straight": m_fStraightWeight = f; break;
				case "longShare": m_fLongStraightShare = f; break;
				case "turn": m_fTurnWeight = f; break;
				case "uturn": m_fUTurnWeight = f; break;
				case "wiggle": m_fWiggleWeight = f; break;
				case "hump": m_fHumpWeight = f; break;
				case "water": m_fWaterTrapWeight = f; break;
				case "hold": m_fHoldBearing = f; break;
				case "standing": m_fStandingWeight = f; break;
				case "crouch": m_fCrouchWeight = f; break;
				case "prone": m_fProneWeight = f; break;
				case "minCover": m_fMinCover = f; break;
				case "checkCover": m_bCheckCover = B(v); break;
				case "exposure": m_fEntranceExposure = f; break;
				case "targetCover": m_fTargetCover = f; break;
				case "slope": m_fSlopeWeight = f; break;
				case "upturn": m_fUpTurnWeight = f; break;
				case "ladder": m_fLadderWeight = f; break;
				case "maxLevels": m_iMaxLevelChanges = i; break;
				case "entrances": m_iExtraEntrances = i; break;
				case "entranceSpacing": m_fEntranceSpacing = f; break;
				case "entranceTol": m_fEntranceTolerance = f; break;
				case "eStair": m_bEntranceStaircase = B(v); break;
				case "eHole": m_bEntranceHole = B(v); break;
				case "eRocky": m_bEntranceRocky = B(v); break;
				case "eHill": m_bEntranceHillCrawl = B(v); break;
				case "masksDoor": m_bMasksAtDoorways = B(v); break;
				case "masksAll": m_bMasksAtAllJoints = B(v); break;
				case "avoid": m_bAvoidExisting = B(v); break;
				case "avoidWorld": m_bAvoidWorld = B(v); break;
				case "ignorePlants": m_bIgnorePlants = B(v); break;
				case "blockers": m_bLightBlockers = B(v); break;
				case "maxRun": m_fMaxStraightRun = f; break;
				case "kit": m_iKit = i; break;
			}
		}
	}
}

//! One piece in a planned layout
class SP_TunnelPlaced
{
	int m_iPiece;
	vector m_vPos;
	float m_fYaw;
	bool m_bSolid = true;		// masks aren't
	vector m_vCentre;			// its box, for overlap checks
	vector m_vHalf;
	float m_fLowY;
	float m_fHighY;
}

//! A socket nobody has attached to yet
class SP_TunnelOpen
{
	vector m_vPos;
	vector m_vDir;
	int m_iSize;
	int m_iRole;
	int m_iOwner;
	int m_iBranch;
	bool m_bGrow = true;		// false: close it off (side doors not taken)
}

class SP_TunnelBranch
{
	bool m_bMain;
	float m_fLength;
	float m_fBudget;
	float m_fBearing;
	float m_fSinceRoom;
	float m_fRun;			// metres since the last piece that breaks the line of sight
	int m_iFromEntrance;
}

//! A box of something already in the world to keep clear of
class SP_TunnelObstacle : SP_TunnelPlaced
{
	string m_sName;
}

class SP_TunnelLayout
{
	int m_iSeed;
	ref array<ref SP_TunnelPlaced> m_aPlaced = {};
	float m_fLength;
	int m_iRooms;
	int m_iEntrances;
	int m_iCaps;
	int m_iForcedCaps;
	int m_iOpenLeft;
	int m_iLevelChanges;
	int m_iMasks;
	float m_fCost;
	ref array<vector> m_aEntrancePoints = {};	// where the new entrances' openings meet the surface, for cutting holes
	int m_iFailReach;
	int m_iFailCover;
	int m_iFailOverlap;
	int m_iFailObstacle;
	int m_iFailWorld;
	int m_iRefusals;
	ref array<string> m_aRefused = {};

	string Refusals()
	{
		return string.Format("pieces refused: %1 too far from the start, %2 not enough earth over them, %3 into this network, %4 into tunnels already in the world, %5 into other things in the world (cliffs, rocks, buildings)", m_iFailReach, m_iFailCover, m_iFailOverlap, m_iFailObstacle, m_iFailWorld);
	}

	string Summary()
	{
		string text = string.Format("seed %1: %2 pieces, %3 m of tunnel, %4 rooms, %5 extra entrances, %6 dead ends (%7 forced), %8 level changes, %9 left open", m_iSeed, m_aPlaced.Count(), Math.Round(m_fLength), m_iRooms, m_iEntrances, m_iCaps, m_iForcedCaps, m_iLevelChanges, m_iOpenLeft);
		return text + string.Format(", %1 masks", m_iMasks);
	}
}

class SP_TunnelGrower
{
	protected static const float OVERLAP_MARGIN = 0.25;
	protected static const int MOST_PIECES = 3000;

	protected SP_TunnelCatalog m_Catalog;
	protected SP_TunnelGenSettings m_Set;
	protected WorldEditorAPI m_Api;
	protected ref array<ref SP_TunnelObstacle> m_aObstacles;
	protected BaseWorld m_World;
	protected ref array<IEntity> m_aIgnore = {};
	protected IEntity m_LastHit;
	protected ref RandomGenerator m_Rand = new RandomGenerator();
	protected ref SP_TunnelLayout m_Layout;
	protected ref array<ref SP_TunnelOpen> m_aOpen = {};
	protected ref array<ref SP_TunnelBranch> m_aBranches = {};
	protected ref array<vector> m_aEntrances = {};
	protected vector m_vStart;
	protected bool m_bStartIsEntrance;
	protected int m_iStartPlaced;

	// Indices into the catalog, by what they're for
	protected ref array<int> m_aCorridor = {};
	protected ref array<int> m_aRooms = {};
	protected ref array<int> m_aEntrancePieces = {};
	protected int m_aCap[3];
	protected int m_aDoorway[3];
	protected int m_aMask[3];
	protected int m_iDoorCap = -1;

	//------------------------------------------------------------------------------------------------
	void SP_TunnelGrower(SP_TunnelCatalog catalog, SP_TunnelGenSettings settings, WorldEditorAPI api, array<ref SP_TunnelObstacle> obstacles)
	{
		m_Catalog = catalog;
		m_Set = settings;
		m_Api = api;
		m_aObstacles = obstacles;
		for (int s = 0; s < 3; s++)
		{
			m_aCap[s] = -1;
			m_aDoorway[s] = -1;
			m_aMask[s] = -1;
		}

		foreach (int index, SP_TunnelPieceDef piece : m_Catalog.m_aPieces)
		{
			switch (piece.m_iKind)
			{
				case SP_TunnelKind.ROOM:
				{
					if (m_Set.m_bLargeRooms || !piece.IsLarge())
						m_aRooms.Insert(index);

					break;
				}
				case SP_TunnelKind.ENTRANCE:
				{
					if (EntranceAllowed(piece.m_sName))
						m_aEntrancePieces.Insert(index);

					break;
				}
				case SP_TunnelKind.CAP:
				{
					m_aCap[piece.m_iSize] = index;
					break;
				}
				case SP_TunnelKind.DOORWAY:
				{
					m_aDoorway[piece.m_iSize] = index;
					break;
				}
				case SP_TunnelKind.DOORCAP:
				{
					m_iDoorCap = index;
					break;
				}
				case SP_TunnelKind.MASK:
				{
					m_aMask[piece.m_iSize] = index;
					break;
				}
				default:
				{
					m_aCorridor.Insert(index);
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	protected bool EntranceAllowed(string name)
	{
		if (name == "Entrance_Floor_Staircase")
			return m_Set.m_bEntranceStaircase;

		if (name == "Entrance_Floor_Hole")
			return m_Set.m_bEntranceHole;

		if (name == "Entrance_Rocky")
			return m_Set.m_bEntranceRocky;

		if (name == "Entrance_Hill_Crawl")
			return m_Set.m_bEntranceHillCrawl;

		return false;
	}

	//================================================================================================
	// Space: yaw-only transforms
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	//! A local vector turned by a yaw, the same way the engine turns an entity (forward +Z goes to sin, cos)
	static vector Rot(vector v, float yaw)
	{
		float r = yaw * Math.DEG2RAD;
		float c = Math.Cos(r);
		float s = Math.Sin(r);
		return Vector(v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c);
	}

	//------------------------------------------------------------------------------------------------
	static float YawOf(vector dir)
	{
		return Math.Atan2(dir[0], dir[2]) * Math.RAD2DEG;
	}

	//------------------------------------------------------------------------------------------------
	//! Where a piece goes so that its socket meets an open socket, facing it
	static void Attach(vector openPos, vector openDir, SP_TunnelSocketDef socket, out vector pos, out float yaw)
	{
		yaw = YawOf(-openDir) - YawOf(socket.m_vDir);
		yaw = yaw - 360 * Math.Round(yaw / 360);
		pos = openPos - Rot(socket.m_vPos, yaw);
	}

	//------------------------------------------------------------------------------------------------
	protected SP_TunnelPlaced MakePlaced(int pieceIndex, vector pos, float yaw)
	{
		SP_TunnelPieceDef piece = m_Catalog.m_aPieces[pieceIndex];
		SP_TunnelPlaced placed = new SP_TunnelPlaced();
		placed.m_iPiece = pieceIndex;
		placed.m_vPos = pos;
		placed.m_fYaw = yaw;
		placed.m_bSolid = piece.m_iKind != SP_TunnelKind.MASK;
		vector mid = (piece.m_vMin + piece.m_vMax) * 0.5;
		vector half = (piece.m_vMax - piece.m_vMin) * 0.5;
		placed.m_vCentre = pos + Rot(mid, yaw);
		placed.m_vHalf = Vector(Math.Max(half[0] - OVERLAP_MARGIN, 0.05), half[1], Math.Max(half[2] - OVERLAP_MARGIN, 0.05));
		placed.m_fLowY = pos[1] + piece.m_vMin[1] + OVERLAP_MARGIN;
		placed.m_fHighY = pos[1] + piece.m_vMax[1] - OVERLAP_MARGIN;
		return placed;
	}

	//------------------------------------------------------------------------------------------------
	//! Do two placed pieces' boxes overlap (turned boxes, tested on the ground plane, then in height)
	protected bool Overlaps(SP_TunnelPlaced a, SP_TunnelPlaced b)
	{
		if (a.m_fHighY < b.m_fLowY || b.m_fHighY < a.m_fLowY)
			return false;

		vector axA = Rot("1 0 0", a.m_fYaw);
		vector azA = Rot("0 0 1", a.m_fYaw);
		vector axB = Rot("1 0 0", b.m_fYaw);
		vector azB = Rot("0 0 1", b.m_fYaw);
		vector between = b.m_vCentre - a.m_vCentre;
		between[1] = 0;
		array<vector> axes = {axA, azA, axB, azB};
		foreach (vector axis : axes)
		{
			float rA = a.m_vHalf[0] * Math.AbsFloat(vector.Dot(axA, axis)) + a.m_vHalf[2] * Math.AbsFloat(vector.Dot(azA, axis));
			float rB = b.m_vHalf[0] * Math.AbsFloat(vector.Dot(axB, axis)) + b.m_vHalf[2] * Math.AbsFloat(vector.Dot(azB, axis));
			if (Math.AbsFloat(vector.Dot(between, axis)) > rA + rB)
				return false;
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	protected SP_TunnelObstacle HitsObstacle(SP_TunnelPlaced placed)
	{
		if (!m_aObstacles)
			return null;

		foreach (SP_TunnelObstacle obstacle : m_aObstacles)
		{
			if (Overlaps(placed, obstacle))
				return obstacle;
		}

		return null;
	}

	//------------------------------------------------------------------------------------------------
	//! What the world check leaves out: the start piece and whatever is about to be replaced
	void SetWorld(BaseWorld world, array<IEntity> ignore)
	{
		m_World = world;
		m_aIgnore.Clear();
		if (ignore)
			m_aIgnore.Copy(ignore);
	}

	//------------------------------------------------------------------------------------------------
	protected bool WorldFilter(notnull IEntity e, vector start = "0 0 0", vector dir = "0 0 0")
	{
		IEntity root = e.GetRootParent();
		if (m_aIgnore.Contains(e) || (root && m_aIgnore.Contains(root)))
			return false;

		if (m_Set.m_bIgnorePlants && Tree.Cast(e))
			return false;

		EntityPrefabData data = e.GetPrefabData();
		if (data)
		{
			string name = data.GetPrefabName();
			// Tunnel pieces have their own check; plants don't reach underground
			if (m_Catalog.IndexOfPrefab(name) >= 0)
				return false;

			name.ToLower();
			if (m_Set.m_bIgnorePlants && (name.Contains("vegetation") || name.Contains("/plant") || name.Contains("grass")))
				return false;
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! Does anything solid in the world (cliffs, rocks, buildings, not the ground) reach into the piece's box. Uses the
	//! real collision, so a tunnel can go under an overhang or close by a rock
	protected IEntity WorldHit(SP_TunnelPlaced placed)
	{
		if (!m_World || !m_Set.m_bAvoidWorld)
			return null;

		TraceOBB box = new TraceOBB();
		vector axes[4];
		Math3D.AnglesToMatrix(Vector(placed.m_fYaw, 0, 0), axes);
		box.Mat[0] = axes[0];
		box.Mat[1] = axes[1];
		box.Mat[2] = axes[2];
		float midY = (placed.m_fLowY + placed.m_fHighY) * 0.5;
		float halfY = Math.Max((placed.m_fHighY - placed.m_fLowY) * 0.5, 0.05);
		box.Start = Vector(placed.m_vCentre[0], midY, placed.m_vCentre[2]);
		box.Mins = Vector(-placed.m_vHalf[0], -halfY, -placed.m_vHalf[2]);
		box.Maxs = Vector(placed.m_vHalf[0], halfY, placed.m_vHalf[2]);
		box.Flags = TraceFlags.ENTS;
		box.LayerMask = EPhysicsLayerPresets.Main;
		if (m_World.TracePosition(box, WorldFilter) < 0)
			return box.TraceEnt;

		return null;
	}

	//------------------------------------------------------------------------------------------------
	//! Earth over the top of a piece: the least, over the piece's real roof (measured into the catalog every metre) if
	//! known, otherwise over its box (the corners and the middle, at the box's top)
	protected float CoverOver(SP_TunnelPlaced placed)
	{
		SP_TunnelPieceDef piece = m_Catalog.m_aPieces[placed.m_iPiece];
		if (!piece.m_aTops.IsEmpty())
		{
			float lowest = 100000;
			foreach (vector roof : piece.m_aTops)
			{
				vector over = placed.m_vPos + Rot(roof, placed.m_fYaw);
				lowest = Math.Min(lowest, m_Api.GetTerrainSurfaceY(over[0], over[2]) - over[1]);
			}

			return lowest;
		}

		float top = placed.m_vPos[1] + piece.m_vMax[1];
		float least = 100000;
		for (int corner = 0; corner < 5; corner++)
		{
			vector local = (piece.m_vMin + piece.m_vMax) * 0.5;
			if (corner < 4)
			{
				local[0] = piece.m_vMin[0];
				if (corner == 1 || corner == 2)
					local[0] = piece.m_vMax[0];

				local[2] = piece.m_vMin[2];
				if (corner >= 2)
					local[2] = piece.m_vMax[2];
			}

			vector at = placed.m_vPos + Rot(local, placed.m_fYaw);
			least = Math.Min(least, m_Api.GetTerrainSurfaceY(at[0], at[2]) - top);
		}

		return least;
	}

	//------------------------------------------------------------------------------------------------
	//! Can this piece go here: nothing of ours or the world's in the way (except the pieces it joins), within reach of
	//! the start, and enough earth over it
	protected bool Fits(SP_TunnelPlaced placed, array<int> except, float needCover)
	{
		string name = m_Catalog.m_aPieces[placed.m_iPiece].m_sName;
		float away = vector.DistanceXZ(placed.m_vCentre, m_vStart);
		if (away > m_Set.m_fMaxReach)
		{
			m_Layout.m_iFailReach++;
			Refused(string.Format("%1 at %2: %3 m from the start, more than the reach", name, placed.m_vPos, Math.Round(away)));
			return false;
		}

		if (needCover > -1000)
		{
			float cover = CoverOver(placed);
			if (cover < needCover)
			{
				m_Layout.m_iFailCover++;
				Refused(string.Format("%1 at %2: %3 m of earth over it, needs %4", name, placed.m_vPos, cover.ToString(5, 2), needCover.ToString(4, 2)));
				return false;
			}
		}

		foreach (int index, SP_TunnelPlaced other : m_Layout.m_aPlaced)
		{
			if (!other.m_bSolid || except.Contains(index))
				continue;

			if (Overlaps(placed, other))
			{
				m_Layout.m_iFailOverlap++;
				Refused(string.Format("%1 at %2: runs into %3 of this network", name, placed.m_vPos, m_Catalog.m_aPieces[other.m_iPiece].m_sName));
				return false;
			}
		}

		SP_TunnelObstacle hit = HitsObstacle(placed);
		if (hit)
		{
			m_Layout.m_iFailObstacle++;
			Refused(string.Format("%1 at %2: runs into %3 already in the world at %4", name, placed.m_vPos, hit.m_sName, hit.m_vPos));
			return false;
		}

		IEntity thing = WorldHit(placed);
		if (thing)
		{
			m_Layout.m_iFailWorld++;
			string thingName = thing.ClassName();
			if (thing.GetPrefabData())
				thingName = thing.GetPrefabData().GetPrefabName();

			Refused(string.Format("%1 at %2: runs into %3 at %4", name, placed.m_vPos, thingName, thing.GetOrigin()));
			return false;
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! The first few refusals of a layout go in the log, so it's clear what's stopping it
	protected void Refused(string why)
	{
		m_Layout.m_iRefusals++;
		if (m_Layout.m_iRefusals <= 12)
			m_Layout.m_aRefused.Insert(why);
	}

	//------------------------------------------------------------------------------------------------
	protected int Add(SP_TunnelPlaced placed)
	{
		m_Layout.m_aPlaced.Insert(placed);
		return m_Layout.m_aPlaced.Count() - 1;
	}

	//------------------------------------------------------------------------------------------------
	protected void Mask(int size, vector pos, vector dir)
	{
		if (size < 0 || size > 2 || m_aMask[size] < 0)
			return;

		Add(MakePlaced(m_aMask[size], pos, YawOf(dir)));
		m_Layout.m_iMasks++;
	}

	//------------------------------------------------------------------------------------------------
	//! The open sockets a placed piece adds, all but the one it was attached by
	protected void OpenSockets(int placedIndex, int except, int branch)
	{
		SP_TunnelPlaced placed = m_Layout.m_aPlaced[placedIndex];
		SP_TunnelPieceDef piece = m_Catalog.m_aPieces[placed.m_iPiece];
		foreach (int s, SP_TunnelSocketDef socket : piece.m_aSockets)
		{
			if (s == except)
				continue;

			SP_TunnelOpen open = new SP_TunnelOpen();
			open.m_vPos = placed.m_vPos + Rot(socket.m_vPos, placed.m_fYaw);
			open.m_vDir = Rot(socket.m_vDir, placed.m_fYaw);
			open.m_iSize = socket.m_iSize;
			open.m_iRole = socket.m_iRole;
			open.m_iOwner = placedIndex;
			open.m_iBranch = branch;
			m_aOpen.Insert(open);
		}
	}

	//------------------------------------------------------------------------------------------------
	protected int NewBranch(bool main, float bearing, int fromEntrance)
	{
		SP_TunnelBranch branch = new SP_TunnelBranch();
		branch.m_bMain = main;
		branch.m_fBearing = bearing;
		branch.m_iFromEntrance = fromEntrance;
		branch.m_fBudget = m_Rand.RandFloatXY(m_Set.m_fSideBranchMin, Math.Max(m_Set.m_fSideBranchMax, m_Set.m_fSideBranchMin));
		m_aBranches.Insert(branch);
		return m_aBranches.Count() - 1;
	}

	//================================================================================================
	// Growing
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	//! A whole layout from one seed, starting at a piece already in the world
	SP_TunnelLayout Grow(int seed, int startPiece, vector startPos, float startYaw)
	{
		m_Rand.SetSeed(seed);
		m_Layout = new SP_TunnelLayout();
		m_Layout.m_iSeed = seed;
		m_aOpen.Clear();
		m_aBranches.Clear();
		m_aEntrances.Clear();
		m_vStart = startPos;

		// The start piece is already there: it's only in the layout so nothing grows back into it
		SP_TunnelPlaced start = MakePlaced(startPiece, startPos, startYaw);
		m_iStartPlaced = Add(start);
		SP_TunnelPieceDef startDef = m_Catalog.m_aPieces[startPiece];
		bool startIsEntrance = startDef.m_iKind == SP_TunnelKind.ENTRANCE;
		m_bStartIsEntrance = startIsEntrance;
		if (startIsEntrance)
			m_aEntrances.Insert(startPos);

		bool first = true;
		foreach (int s, SP_TunnelSocketDef socket : startDef.m_aSockets)
		{
			vector dir = Rot(socket.m_vDir, startYaw);
			// Whatever the start piece, right by it the tunnel may be shallow, and has to get deeper as it goes
			int fromEntrance = 0;

			int branch = NewBranch(first, YawOf(dir), fromEntrance);
			SP_TunnelOpen open = new SP_TunnelOpen();
			open.m_bGrow = first || m_Rand.RandFloat01() < m_Set.m_fBranchChance;
			first = false;
			open.m_vPos = startPos + Rot(socket.m_vPos, startYaw);
			open.m_vDir = dir;
			open.m_iSize = socket.m_iSize;
			open.m_iRole = socket.m_iRole;
			open.m_iOwner = m_iStartPlaced;
			open.m_iBranch = branch;
			m_aOpen.Insert(open);
		}

		while (!m_aOpen.IsEmpty() && m_Layout.m_aPlaced.Count() < MOST_PIECES)
		{
			// The main way on first, so the length goes where it should; then side branches in the order they opened
			int pick = 0;
			foreach (int o, SP_TunnelOpen candidate : m_aOpen)
			{
				if (m_aBranches[candidate.m_iBranch].m_bMain && candidate.m_bGrow)
				{
					pick = o;
					break;
				}
			}

			SP_TunnelOpen next = m_aOpen[pick];
			m_aOpen.Remove(pick);
			Handle(next);
		}

		m_Layout.m_iOpenLeft = m_aOpen.Count();
		Score();
		return m_Layout;
	}

	//------------------------------------------------------------------------------------------------
	protected void Handle(SP_TunnelOpen open)
	{
		if (open.m_iRole == SP_TunnelRole.DOOR)
		{
			HandleDoor(open);
			return;
		}

		if (open.m_iRole != SP_TunnelRole.PATH)
			return;

		SP_TunnelBranch branch = m_aBranches[open.m_iBranch];
		bool done = m_Layout.m_fLength >= m_Set.m_fTargetLength || !open.m_bGrow;
		if (!branch.m_bMain && branch.m_fLength >= branch.m_fBudget)
			done = true;

		if (done)
		{
			EndHere(open, false);
			return;
		}

		// A room, when it's been long enough since the last
		if (m_Layout.m_iRooms < m_Set.m_iMaxRooms && branch.m_fSinceRoom >= m_Set.m_fRoomSpacing && m_Rand.RandFloat01() < 0.5)
		{
			if (TryRoom(open, branch))
				return;
		}

		if (TryCorridor(open, branch))
			return;

		// Nothing fits here: a room might, as it goes somewhere else entirely
		if (m_Layout.m_iRooms < m_Set.m_iMaxRooms && TryRoom(open, branch))
			return;

		EndHere(open, true);
	}

	//------------------------------------------------------------------------------------------------
	//! Earth the piece needs over it: less right by an entrance, where the tunnel has only just gone in
	protected float NeedCover(SP_TunnelBranch branch)
	{
		// switched off: anything goes (Fits takes anything under -1000 as "don't check")
		if (!m_Set.m_bCheckCover)
			return -100000;

		// From an entrance its first pieces may stick out of the ground (the mouth's surroundings get shaped by hand),
		// then have to be under it within a few pieces; from anything else, a little earth right away
		if (m_bStartIsEntrance)
			return Math.Min(m_Set.m_fMinCover, -m_Set.m_fEntranceExposure + branch.m_iFromEntrance * 0.8);

		return Math.Min(m_Set.m_fMinCover, 0.2 + branch.m_iFromEntrance * 0.6);
	}

	//------------------------------------------------------------------------------------------------
	//! How heavily each corridor piece is weighted
	protected float KindWeight(SP_TunnelPieceDef piece)
	{
		switch (piece.m_iKind)
		{
			case SP_TunnelKind.STRAIGHT:
			{
				float share = m_Set.m_fLongStraightShare;
				if (piece.m_sName.Contains("7.5"))
					return m_Set.m_fStraightWeight * share;

				return m_Set.m_fStraightWeight * (1 - share);
			}
			case SP_TunnelKind.TURN: return m_Set.m_fTurnWeight * 0.5;
			case SP_TunnelKind.BEND: return m_Set.m_fWiggleWeight * 0.5;
			case SP_TunnelKind.HUMP: return m_Set.m_fHumpWeight;
			case SP_TunnelKind.WATER: return m_Set.m_fWaterTrapWeight;
			case SP_TunnelKind.SLOPE: return m_Set.m_fSlopeWeight;
			case SP_TunnelKind.UPTURN: return m_Set.m_fUpTurnWeight * 0.5;
			case SP_TunnelKind.UTURN: return m_Set.m_fUTurnWeight;
			case SP_TunnelKind.LADDER: return m_Set.m_fLadderWeight;
		}

		return 0;
	}

	//------------------------------------------------------------------------------------------------
	protected bool IsLevelChange(int kind)
	{
		return kind == SP_TunnelKind.SLOPE || kind == SP_TunnelKind.UPTURN || kind == SP_TunnelKind.LADDER;
	}

	//------------------------------------------------------------------------------------------------
	//! Pieces you can't see along: after one of these, the straight run starts again
	protected bool BreaksSight(int kind)
	{
		return kind == SP_TunnelKind.TURN || kind == SP_TunnelKind.BEND || kind == SP_TunnelKind.UTURN || kind == SP_TunnelKind.UPTURN || kind == SP_TunnelKind.LADDER || kind == SP_TunnelKind.ROOM;
	}

	//------------------------------------------------------------------------------------------------
	//! Of a piece's other sockets, the way on: facing most nearly away from the one it was entered by, nearest in height
	protected int WayOn(SP_TunnelPieceDef piece, int entry)
	{
		SP_TunnelSocketDef entrySocket = piece.m_aSockets[entry];
		int best = -1;
		float bestScore = 100000;
		foreach (int s, SP_TunnelSocketDef socket : piece.m_aSockets)
		{
			if (s == entry || socket.m_iRole != SP_TunnelRole.PATH)
				continue;

			float score = vector.Dot(socket.m_vDir, entrySocket.m_vDir) * 2 + Math.AbsFloat(socket.m_vPos[1] - entrySocket.m_vPos[1]) * 0.3;
			if (score < bestScore)
			{
				bestScore = score;
				best = s;
			}
		}

		return best;
	}

	//------------------------------------------------------------------------------------------------
	protected bool TryCorridor(SP_TunnelOpen open, SP_TunnelBranch branch)
	{
		// Every corridor piece of this size, entered by each socket that fits, with its weight
		array<int> optionPiece = {};
		array<int> optionSocket = {};
		array<float> optionWeight = {};
		float depthNow = m_Api.GetTerrainSurfaceY(open.m_vPos[0], open.m_vPos[2]) - open.m_vPos[1];
		foreach (int index : m_aCorridor)
		{
			SP_TunnelPieceDef piece = m_Catalog.m_aPieces[index];
			if (piece.m_iSize != open.m_iSize)
				continue;

			float weight = KindWeight(piece);
			if (weight <= 0)
				continue;

			if (IsLevelChange(piece.m_iKind) && m_Layout.m_iLevelChanges >= m_Set.m_iMaxLevelChanges)
				continue;

			// Seen far enough straight along already: only something that breaks the line of sight
			bool breaks = BreaksSight(piece.m_iKind);
			if (!breaks && m_Set.m_fMaxStraightRun > 0 && branch.m_fRun >= m_Set.m_fMaxStraightRun - 0.5)
				continue;

			foreach (int s, SP_TunnelSocketDef socket : piece.m_aSockets)
			{
				if (socket.m_iRole != SP_TunnelRole.PATH || socket.m_iSize != open.m_iSize)
					continue;

				// Where it would come out, and how well that keeps the depth and the heading
				vector pos;
				float yaw;
				SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, socket, pos, yaw);
				int onIndex = WayOn(piece, s);
				float w = weight;
				if (onIndex >= 0)
				{
					SP_TunnelSocketDef on = piece.m_aSockets[onIndex];
					vector outPos = pos + Rot(on.m_vPos, yaw);
					vector outDir = Rot(on.m_vDir, yaw);
					float depthAfter = m_Api.GetTerrainSurfaceY(outPos[0], outPos[2]) - outPos[1];
					float wantDepth = m_Set.m_fTargetCover + 1.3;
					float errorAfter = Math.AbsFloat(depthAfter - wantDepth);
					float errorNow = Math.AbsFloat(depthNow - wantDepth);
					w *= 1 / (1 + 0.6 * Math.Max(errorAfter - errorNow + 0.5, 0));
					if (branch.m_bMain && m_Set.m_fHoldBearing > 0)
					{
						float off = (YawOf(outDir) - branch.m_fBearing) * Math.DEG2RAD;
						w *= Math.Max(0.05, 1 + m_Set.m_fHoldBearing * Math.Cos(off));
					}
				}

				if (!breaks && m_Set.m_fMaxStraightRun > 0 && onIndex >= 0)
				{
					float runAfter = branch.m_fRun + vector.Distance(piece.m_aSockets[onIndex].m_vPos, socket.m_vPos);
					if (runAfter > m_Set.m_fMaxStraightRun)
						continue;
				}

				optionPiece.Insert(index);
				optionSocket.Insert(s);
				optionWeight.Insert(w);
			}
		}

		// Picked by weight, the next one if it doesn't fit, a dozen tries at most
		for (int attempt = 0; attempt < 12 && !optionPiece.IsEmpty(); attempt++)
		{
			float total = 0;
			foreach (float ow : optionWeight)
			{
				total += ow;
			}

			if (total <= 0)
				break;

			float roll = m_Rand.RandFloat01() * total;
			int chosen = optionWeight.Count() - 1;
			for (int c = 0; c < optionWeight.Count(); c++)
			{
				roll -= optionWeight[c];
				if (roll <= 0)
				{
					chosen = c;
					break;
				}
			}

			int pieceIndex = optionPiece[chosen];
			int socketIndex = optionSocket[chosen];
			optionPiece.Remove(chosen);
			optionSocket.Remove(chosen);
			optionWeight.Remove(chosen);
			if (PlaceCorridor(open, branch, pieceIndex, socketIndex))
				return true;
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	protected bool PlaceCorridor(SP_TunnelOpen open, SP_TunnelBranch branch, int pieceIndex, int socketIndex)
	{
		SP_TunnelPieceDef piece = m_Catalog.m_aPieces[pieceIndex];
		vector pos;
		float yaw;
		SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, piece.m_aSockets[socketIndex], pos, yaw);
		SP_TunnelPlaced placed = MakePlaced(pieceIndex, pos, yaw);
		array<int> except = {open.m_iOwner};
		if (!Fits(placed, except, NeedCover(branch)))
			return false;

		int placedIndex = Add(placed);
		if (IsLevelChange(piece.m_iKind))
			m_Layout.m_iLevelChanges++;

		JointMask(open);

		// The way on carries the branch; any other socket (the ladder's other level) starts a side branch or is closed
		int onIndex = WayOn(piece, socketIndex);
		float chord = 0;
		foreach (int s, SP_TunnelSocketDef socket : piece.m_aSockets)
		{
			if (s == socketIndex)
				continue;

			SP_TunnelOpen next = new SP_TunnelOpen();
			next.m_vPos = pos + Rot(socket.m_vPos, yaw);
			next.m_vDir = Rot(socket.m_vDir, yaw);
			next.m_iSize = socket.m_iSize;
			next.m_iRole = socket.m_iRole;
			next.m_iOwner = placedIndex;
			if (s == onIndex)
			{
				next.m_iBranch = open.m_iBranch;
				chord = vector.Distance(next.m_vPos, open.m_vPos);
			}
			else
			{
				next.m_iBranch = NewBranch(false, YawOf(next.m_vDir), branch.m_iFromEntrance + 1);
				next.m_bGrow = m_Rand.RandFloat01() < m_Set.m_fBranchChance;
			}

			m_aOpen.Insert(next);
		}

		branch.m_fLength += chord;
		branch.m_fSinceRoom += chord;
		if (BreaksSight(piece.m_iKind))
			branch.m_fRun = 0;
		else
			branch.m_fRun += chord;

		branch.m_iFromEntrance++;
		m_Layout.m_fLength += chord;
		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! A mask over the joint at this socket, if asked for there
	protected void JointMask(SP_TunnelOpen open)
	{
		if (open.m_iSize > SP_TunnelSize.P)
			return;

		SP_TunnelPieceDef owner = m_Catalog.m_aPieces[m_Layout.m_aPlaced[open.m_iOwner].m_iPiece];
		bool atDoorway = owner.m_iKind == SP_TunnelKind.DOORWAY;
		if (m_Set.m_bMasksAtAllJoints || (atDoorway && m_Set.m_bMasksAtDoorways))
			Mask(open.m_iSize, open.m_vPos, open.m_vDir);
	}

	//------------------------------------------------------------------------------------------------
	//! A doorway onto the end of this corridor, and a room on it, by one of the room's doorframes
	protected bool TryRoom(SP_TunnelOpen open, SP_TunnelBranch branch)
	{
		if (m_aRooms.IsEmpty())
			return false;

		// A kit whose rooms have the tunnel's own openings: the room straight onto the corridor
		int doorwayIndex = m_aDoorway[open.m_iSize];
		if (doorwayIndex < 0)
			return TryRoomDirect(open, branch);

		SP_TunnelPieceDef doorway = m_Catalog.m_aPieces[doorwayIndex];
		int pathSocket = -1;
		int roomSideSocket = -1;
		foreach (int ds, SP_TunnelSocketDef doorSocket : doorway.m_aSockets)
		{
			if (doorSocket.m_iRole == SP_TunnelRole.PATH)
				pathSocket = ds;
			else if (doorSocket.m_iRole == SP_TunnelRole.ROOMSIDE)
				roomSideSocket = ds;
		}

		if (pathSocket < 0 || roomSideSocket < 0)
			return false;

		vector doorPos;
		float doorYaw;
		SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, doorway.m_aSockets[pathSocket], doorPos, doorYaw);
		SP_TunnelPlaced doorPlaced = MakePlaced(doorwayIndex, doorPos, doorYaw);
		array<int> exceptDoor = {open.m_iOwner};
		if (!Fits(doorPlaced, exceptDoor, NeedCover(branch)))
			return false;

		vector frontPos = doorPos + Rot(doorway.m_aSockets[roomSideSocket].m_vPos, doorYaw);
		vector frontDir = Rot(doorway.m_aSockets[roomSideSocket].m_vDir, doorYaw);

		// A few rooms, each by a few of its doorframes
		for (int attempt = 0; attempt < 8; attempt++)
		{
			int roomIndex = m_aRooms[m_Rand.RandInt(0, m_aRooms.Count())];
			SP_TunnelPieceDef room = m_Catalog.m_aPieces[roomIndex];
			int doorCount = room.m_aSockets.Count();
			if (doorCount == 0)
				continue;

			int entryDoor = m_Rand.RandInt(0, doorCount);
			vector roomPos;
			float roomYaw;
			SP_TunnelGrower.Attach(frontPos, frontDir, room.m_aSockets[entryDoor], roomPos, roomYaw);
			SP_TunnelPlaced roomPlaced = MakePlaced(roomIndex, roomPos, roomYaw);
			int doorWillBe = m_Layout.m_aPlaced.Count();
			array<int> exceptRoom = {doorWillBe, open.m_iOwner};
			if (!Fits(roomPlaced, exceptRoom, NeedCover(branch)))
				continue;

			// Both fit: build them
			int doorPlacedIndex = Add(doorPlaced);
			int roomPlacedIndex = Add(roomPlaced);
			if (m_Set.m_bMasksAtDoorways || m_Set.m_bMasksAtAllJoints)
				Mask(open.m_iSize, open.m_vPos, open.m_vDir);

			m_Layout.m_iRooms++;
			RoomDoors(roomPlacedIndex, entryDoor, open.m_iBranch, branch);
			return true;
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! A room joined straight onto the corridor, by one of its openings of the corridor's size
	protected bool TryRoomDirect(SP_TunnelOpen open, SP_TunnelBranch branch)
	{
		for (int attempt = 0; attempt < 8; attempt++)
		{
			int roomIndex = m_aRooms[m_Rand.RandInt(0, m_aRooms.Count())];
			SP_TunnelPieceDef room = m_Catalog.m_aPieces[roomIndex];
			array<int> fitting = {};
			foreach (int rs, SP_TunnelSocketDef roomSocket : room.m_aSockets)
			{
				if (roomSocket.m_iRole == SP_TunnelRole.PATH && roomSocket.m_iSize == open.m_iSize)
					fitting.Insert(rs);
			}

			if (fitting.IsEmpty())
				continue;

			int entryDoor = fitting[m_Rand.RandInt(0, fitting.Count())];
			vector roomPos;
			float roomYaw;
			SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, room.m_aSockets[entryDoor], roomPos, roomYaw);
			SP_TunnelPlaced roomPlaced = MakePlaced(roomIndex, roomPos, roomYaw);
			array<int> except = {open.m_iOwner};
			if (!Fits(roomPlaced, except, NeedCover(branch)))
				continue;

			int roomPlacedIndex = Add(roomPlaced);
			JointMask(open);
			m_Layout.m_iRooms++;
			RoomDoors(roomPlacedIndex, entryDoor, open.m_iBranch, branch);
			return true;
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! A room's other doorframes: on the main way one carries on (the one most nearly along its heading), the rest are
	//! side branches now and then, and closed off otherwise
	protected void RoomDoors(int roomPlacedIndex, int entryDoor, int branchIndex, SP_TunnelBranch branch)
	{
		SP_TunnelPlaced placed = m_Layout.m_aPlaced[roomPlacedIndex];
		SP_TunnelPieceDef room = m_Catalog.m_aPieces[placed.m_iPiece];
		int carryOn = -1;
		if (branch.m_bMain)
		{
			float bestAlong = -100;
			foreach (int d, SP_TunnelSocketDef door : room.m_aSockets)
			{
				if (d == entryDoor)
					continue;

				float off = (YawOf(Rot(door.m_vDir, placed.m_fYaw)) - branch.m_fBearing) * Math.DEG2RAD;
				float along = Math.Cos(off) + m_Rand.RandFloat01() * 0.3;
				if (along > bestAlong)
				{
					bestAlong = along;
					carryOn = d;
				}
			}
		}

		foreach (int s, SP_TunnelSocketDef socket : room.m_aSockets)
		{
			if (s == entryDoor)
				continue;

			SP_TunnelOpen next = new SP_TunnelOpen();
			next.m_vPos = placed.m_vPos + Rot(socket.m_vPos, placed.m_fYaw);
			next.m_vDir = Rot(socket.m_vDir, placed.m_fYaw);
			next.m_iSize = socket.m_iSize;
			next.m_iRole = socket.m_iRole;
			next.m_iOwner = roomPlacedIndex;
			if (s == carryOn)
			{
				next.m_iBranch = branchIndex;
				branch.m_fSinceRoom = 0;
				branch.m_fRun = 0;
			}
			else
			{
				next.m_iBranch = NewBranch(false, YawOf(next.m_vDir), branch.m_iFromEntrance + 2);
				next.m_bGrow = m_Rand.RandFloat01() < m_Set.m_fBranchChance;
			}

			m_aOpen.Insert(next);
		}
	}

	//------------------------------------------------------------------------------------------------
	//! A size for a corridor leaving a room, by the weights
	protected int PickSize()
	{
		float total = m_Set.m_fStandingWeight + m_Set.m_fCrouchWeight + m_Set.m_fProneWeight;
		if (total <= 0)
			return SP_TunnelSize.S;

		float roll = m_Rand.RandFloat01() * total;
		if (roll < m_Set.m_fStandingWeight)
			return SP_TunnelSize.S;

		if (roll < m_Set.m_fStandingWeight + m_Set.m_fCrouchWeight)
			return SP_TunnelSize.C;

		return SP_TunnelSize.P;
	}

	//------------------------------------------------------------------------------------------------
	//! A room's doorframe: a doorway and a corridor on from it, or closed off
	protected void HandleDoor(SP_TunnelOpen open)
	{
		SP_TunnelBranch branch = m_aBranches[open.m_iBranch];
		bool grow = open.m_bGrow && m_Layout.m_fLength < m_Set.m_fTargetLength;
		if (grow)
		{
			int size = PickSize();
			for (int sizeTry = 0; sizeTry < 3; sizeTry++)
			{
				int doorwayIndex = m_aDoorway[size];
				if (doorwayIndex >= 0 && PlaceDoorway(open, branch, doorwayIndex))
					return;

				size = (size + 1) % 3;
			}
		}

		CloseDoor(open);
	}

	//------------------------------------------------------------------------------------------------
	protected bool PlaceDoorway(SP_TunnelOpen open, SP_TunnelBranch branch, int doorwayIndex)
	{
		SP_TunnelPieceDef doorway = m_Catalog.m_aPieces[doorwayIndex];
		foreach (int s, SP_TunnelSocketDef socket : doorway.m_aSockets)
		{
			if (socket.m_iRole != SP_TunnelRole.ROOMSIDE)
				continue;

			vector pos;
			float yaw;
			SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, socket, pos, yaw);
			SP_TunnelPlaced placed = MakePlaced(doorwayIndex, pos, yaw);
			array<int> except = {open.m_iOwner};
			if (!Fits(placed, except, NeedCover(branch)))
				return false;

			int placedIndex = Add(placed);
			OpenSockets(placedIndex, s, open.m_iBranch);
			return true;
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	protected void CloseDoor(SP_TunnelOpen open)
	{
		if (m_iDoorCap < 0)
			return;

		SP_TunnelPieceDef cap = m_Catalog.m_aPieces[m_iDoorCap];
		foreach (SP_TunnelSocketDef socket : cap.m_aSockets)
		{
			if (socket.m_iRole != SP_TunnelRole.ROOMSIDE)
				continue;

			vector pos;
			float yaw;
			SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, socket, pos, yaw);
			Add(MakePlaced(m_iDoorCap, pos, yaw));
			return;
		}
	}

	//------------------------------------------------------------------------------------------------
	//! The end of a corridor: a way out to the surface if one's wanted and the ground fits, otherwise a dead end
	protected void EndHere(SP_TunnelOpen open, bool forced)
	{
		if (m_Layout.m_iEntrances < m_Set.m_iExtraEntrances && TryEntrance(open))
			return;

		m_Layout.m_iCaps++;
		if (forced)
			m_Layout.m_iForcedCaps++;

		// Standing: the blocked path. Crouching and prone: their doorway, closed off
		int capIndex = -1;
		if (open.m_iSize >= 0 && open.m_iSize <= 2)
			capIndex = m_aCap[open.m_iSize];

		if (capIndex >= 0)
		{
			SP_TunnelPieceDef cap = m_Catalog.m_aPieces[capIndex];
			vector pos;
			float yaw;
			SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, cap.m_aSockets[0], pos, yaw);
			Add(MakePlaced(capIndex, pos, yaw));
			JointMask(open);
			return;
		}

		// Crouching and prone have no blocked path: the blocked doorway, where that size's doorway would go
		int doorwayIndex = -1;
		if (open.m_iSize >= 0 && open.m_iSize <= 2)
			doorwayIndex = m_aDoorway[open.m_iSize];

		if (doorwayIndex < 0 || m_iDoorCap < 0)
		{
			Mask(open.m_iSize, open.m_vPos, open.m_vDir);
			return;
		}

		SP_TunnelPieceDef doorway = m_Catalog.m_aPieces[doorwayIndex];
		foreach (SP_TunnelSocketDef socket : doorway.m_aSockets)
		{
			if (socket.m_iRole != SP_TunnelRole.PATH)
				continue;

			vector doorPos;
			float doorYaw;
			SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, socket, doorPos, doorYaw);
			Add(MakePlaced(m_iDoorCap, doorPos, doorYaw));
			Mask(open.m_iSize, open.m_vPos, open.m_vDir);
			return;
		}
	}

	//------------------------------------------------------------------------------------------------
	//! An entrance piece on the end of a corridor, if its top comes out near enough the ground and it's far enough
	//! from the other ways in
	protected bool TryEntrance(SP_TunnelOpen open)
	{
		foreach (vector other : m_aEntrances)
		{
			if (vector.DistanceXZ(other, open.m_vPos) < m_Set.m_fEntranceSpacing)
				return false;
		}

		foreach (int index : m_aEntrancePieces)
		{
			SP_TunnelPieceDef piece = m_Catalog.m_aPieces[index];
			if (piece.m_iSize != open.m_iSize || piece.m_aSockets.IsEmpty())
				continue;

			vector pos;
			float yaw;
			SP_TunnelGrower.Attach(open.m_vPos, open.m_vDir, piece.m_aSockets[0], pos, yaw);
			float top = pos[1] + piece.m_vMax[1];
			float ground = m_Api.GetTerrainSurfaceY(pos[0], pos[2]);
			if (Math.AbsFloat(ground - top) > m_Set.m_fEntranceTolerance)
				continue;

			SP_TunnelPlaced placed = MakePlaced(index, pos, yaw);
			array<int> except = {open.m_iOwner};
			if (!Fits(placed, except, -100000))
				continue;

			Add(placed);
			JointMask(open);
			m_Layout.m_iEntrances++;
			m_aEntrances.Insert(pos);
			m_Layout.m_aEntrancePoints.Insert(Vector(pos[0], ground, pos[2]));
			return true;
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! Lower is better
	protected void Score()
	{
		float cost = 0;
		cost += Math.AbsFloat(m_Set.m_fTargetLength - m_Layout.m_fLength) / Math.Max(m_Set.m_fTargetLength, 1) * 100;
		cost += (m_Set.m_iMaxRooms - m_Layout.m_iRooms) * 10;
		cost += (m_Set.m_iExtraEntrances - m_Layout.m_iEntrances) * 15;
		cost += m_Layout.m_iForcedCaps * 4;
		cost += m_Layout.m_iOpenLeft * 20;
		m_Layout.m_fCost = cost;
	}
}
#endif
