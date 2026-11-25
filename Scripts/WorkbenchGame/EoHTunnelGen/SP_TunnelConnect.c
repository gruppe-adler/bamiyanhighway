#ifdef WORKBENCH
//! Connect mode: several entrances of the kit are selected, and the generator builds the tunnels that join them all.
//! The first is the start (it never moves); the others are "pinned": already in the world, in the layout from the start so
//! nothing grows into them, and each moved a little (within the Connect settings) so its socket meets the tunnel's end.
//! Routes are planned here as spline paths (SP_TunnelSplinePath) that the grower follows like any drawn spline.

//! An entrance already in the world that the network has to reach
class SP_TunnelPin
{
	IEntity m_Entity;
	IEntitySource m_Src;
	string m_sName;
	int m_iPiece;			// catalog index
	int m_iSocket;			// its socket (the inner end)
	vector m_vPos;			// where it is now
	float m_fYaw;
	vector m_vSocketPos;	// world, now
	vector m_vSocketDir;	// world, now: outward, i.e. into the hill, towards the tunnel
	float m_fGridOff;		// how far its direction is from the tunnel's grid (the start's direction in 90 degree steps)
	string m_sSkip;			// not empty: left out, and why
	bool m_bPlanned;
}

//! What happened to one pinned entrance in a layout
class SP_TunnelDocking
{
	string m_sName;
	IEntitySource m_Src;
	bool m_bDocked;
	vector m_vFrom;
	float m_fFromYaw;
	vector m_vPos;		// where it ends up
	float m_fYaw;
	float m_fMove;
	float m_fTurn;
	float m_fRise;
	string m_sWhy;		// when not docked

	string Describe()
	{
		if (m_bDocked)
			return string.Format("%1: connected, moved %2 m, turned %3 degrees, height changed %4 m", m_sName, m_fMove.ToString(-1, 2), m_fTurn.ToString(-1, 1), m_fRise.ToString(-1, 2));

		return string.Format("%1: NOT connected (%2)", m_sName, m_sWhy);
	}
}

class SP_TunnelConnect
{
	protected static const float STUB = 8;		// the route leaves a socket, and arrives at one, along its direction for this far
	protected static const float STEP = 9;		// points along the way
	protected static const float SIDE = 6;		// a branch leaves its parent sideways for this far
	protected static const float RAMP = 30;		// how far from an end the height changes over, from the socket's to the usual depth
	protected static const float KEEP_OFF_ENDS = 10;
	protected static const float KEEP_OFF_TARGET = 30;
	protected static const float JUNCTION_GAP = 12;

	//------------------------------------------------------------------------------------------------
	static float Wrap(float angle)
	{
		return angle - 360 * Math.Round(angle / 360);
	}

	//------------------------------------------------------------------------------------------------
	//! Works out each pin's socket in the world, and whether the tunnels can reach it at all: they only turn in 90 degree
	//! steps from the start's direction, so a pin whose direction is further off that grid than the allowed turn can't dock
	static void Check(SP_TunnelCatalog catalog, SP_TunnelGenSettings cfg, vector startDir, int startSize, notnull array<ref SP_TunnelPin> pins)
	{
		float baseYaw = SP_TunnelGrower.YawOf(startDir);
		// with the gentle curve pieces (5, 10, 15 degrees) the headings come in 5 degree steps, not only in 90
		float gridStep = 90;
		foreach (SP_TunnelPieceDef piece : catalog.m_aPieces)
		{
			if (piece.m_sName == "TT_Curve_5")
				gridStep = 5;
		}
		foreach (SP_TunnelPin pin : pins)
		{
			SP_TunnelPieceDef def = catalog.m_aPieces[pin.m_iPiece];
			pin.m_iSocket = -1;
			foreach (int s, SP_TunnelSocketDef socket : def.m_aSockets)
			{
				if (socket.m_iRole == SP_TunnelRole.PATH)
				{
					pin.m_iSocket = s;
					break;
				}
			}

			if (pin.m_iSocket < 0)
			{
				pin.m_sSkip = "it has no tunnel socket in the catalog";
				continue;
			}

			SP_TunnelSocketDef sock = def.m_aSockets[pin.m_iSocket];
			pin.m_vSocketPos = pin.m_vPos + SP_TunnelGrower.Rot(sock.m_vPos, pin.m_fYaw);
			pin.m_vSocketDir = SP_TunnelGrower.Rot(sock.m_vDir, pin.m_fYaw);
			float want = SP_TunnelGrower.YawOf(-pin.m_vSocketDir);
			float off = Wrap(want - baseYaw);
			pin.m_fGridOff = Math.AbsFloat(off - gridStep * Math.Round(off / gridStep));
			if (!pin.m_sSkip.IsEmpty())
				continue;

			if (sock.m_iSize != startSize)
				pin.m_sSkip = "it is a different tunnel size from the start entrance (no piece joins them)";
			else if (pin.m_fGridOff > cfg.m_fDockTurn + 0.5)
				pin.m_sSkip = string.Format("it points %1 degrees off the tunnel grid (the start entrance's direction in steps of the finest curve piece, 90 degrees without the TT_Curve pieces); it would have to turn more than the allowed %2: raise Max turn to at least %3, or rotate it", Math.Round(pin.m_fGridOff), Math.Round(cfg.m_fDockTurn), Math.Ceil(pin.m_fGridOff));
		}
	}

	//------------------------------------------------------------------------------------------------
	protected static float Flat(vector a, vector b)
	{
		return vector.DistanceXZ(a, b);
	}

	//------------------------------------------------------------------------------------------------
	//! One route's curve: points from -> away from it along fromDir -> straight, a point every STEP -> in front of the pin's
	//! socket -> the socket. Heights: the socket's at both ends, the usual depth under the ground between (eased over RAMP).
	protected static SP_TunnelSplinePath MakeRoute(WorldEditorAPI api, SP_TunnelGenSettings cfg, string name, vector from, vector fromDir, float lead0, SP_TunnelPin pin)
	{
		vector target = pin.m_vSocketPos;
		vector targetDir = pin.m_vSocketDir;
		targetDir[1] = 0;
		if (targetDir.Length() > 0.01)
			targetDir = targetDir * (1 / targetDir.Length());

		float whole = Flat(from, target);
		float lead1 = Math.Min(STUB, whole / 3);
		array<vector> xz = {};
		xz.Insert(from);
		vector first = from + fromDir * lead0;
		xz.Insert(first);
		vector last = target + targetDir * lead1;
		float leg = Flat(first, last);
		int segments = Math.Max(1, Math.Ceil(leg / STEP));
		for (int k = 1; k < segments; k++)
		{
			float t = k;
			t = t / segments;
			xz.Insert(first + (last - first) * t);
		}

		xz.Insert(last);
		xz.Insert(target);

		// How far along each point is
		array<float> along = {};
		float total = 0;
		for (int i = 0; i < xz.Count(); i++)
		{
			if (i > 0)
				total += Flat(xz[i - 1], xz[i]);

			along.Insert(total);
		}

		float y0 = from[1];
		float y1 = target[1];
		float depth = cfg.m_fTargetCover + 1.3;
		SP_TunnelSplinePath path = new SP_TunnelSplinePath();
		path.m_sName = name;
		for (int p = 0; p < xz.Count(); p++)
		{
			vector point = xz[p];
			float mid = api.GetTerrainSurfaceY(point[0], point[2]) - depth;
			float a = Math.Clamp(1 - along[p] / RAMP, 0, 1);
			float b = Math.Clamp(1 - (total - along[p]) / RAMP, 0, 1);
			if (a + b > 1)
			{
				float sum = a + b;
				a = a / sum;
				b = b / sum;
			}

			point[1] = mid * (1 - a - b) + y0 * a + y1 * b;
			if (p == 0)
				point[1] = y0;

			if (p == xz.Count() - 1)
				point[1] = y1;

			path.m_aCurve.Insert(point);
		}

		path.Build(api);
		return path;
	}

	//------------------------------------------------------------------------------------------------
	//! Plans the routes: the main one from the start's socket to the nearest pin, then for every other pin a branch that
	//! leaves the nearest point of the routes so far (sideways, with a junction added there by SP_TunnelSplinePath.Link)
	//! and ends at the pin's socket. Pins that can't be reached (pin.m_sSkip) are left out. False: no route at all.
	static bool Plan(WorldEditorAPI api, SP_TunnelGenSettings cfg, vector startSocketPos, vector startSocketDir, notnull array<ref SP_TunnelPin> pins, notnull array<ref SP_TunnelSplinePath> paths)
	{
		paths.Clear();
		vector fromDir = startSocketDir;
		fromDir[1] = 0;
		if (fromDir.Length() > 0.01)
			fromDir = fromDir * (1 / fromDir.Length());

		array<int> branchOf = {};		// per path: the path it leaves (-1: the main one)
		array<float> branchAt = {};		// and where
		while (true)
		{
			int bestPin = -1;
			float bestDist = 1000000;
			int bestParent = -1;
			float bestS = 0;
			foreach (int i, SP_TunnelPin pin : pins)
			{
				if (pin.m_bPlanned || !pin.m_sSkip.IsEmpty())
					continue;

				float dist = 1000000;
				int parent = -1;
				float parentS = 0;
				if (paths.IsEmpty())
				{
					dist = Flat(startSocketPos, pin.m_vSocketPos);
				}
				else
				{
					foreach (int q, SP_TunnelSplinePath existing : paths)
					{
						float lateral;
						float s = existing.ProjectAll(pin.m_vSocketPos, lateral);
						if (lateral < dist)
						{
							dist = lateral;
							parent = q;
							parentS = s;
						}
					}
				}

				if (dist < bestDist)
				{
					bestDist = dist;
					bestPin = i;
					bestParent = parent;
					bestS = parentS;
				}
			}

			if (bestPin < 0)
				break;

			SP_TunnelPin target = pins[bestPin];
			target.m_bPlanned = true;
			SP_TunnelSplinePath route;
			if (paths.IsEmpty())
			{
				float lead = Math.Min(STUB, Flat(startSocketPos, target.m_vSocketPos) / 3);
				route = MakeRoute(api, cfg, "connect to " + target.m_sName, startSocketPos, fromDir, lead, target);
				branchOf.Insert(-1);
				branchAt.Insert(0);
			}
			else
			{
				// Where it leaves: off the ends of the route it leaves, and not close to another branch's junction
				SP_TunnelSplinePath parentPath = paths[bestParent];
				float low = KEEP_OFF_ENDS;
				float high = Math.Max(low, parentPath.m_fLength - KEEP_OFF_TARGET);
				float at = Math.Clamp(bestS, low, high);
				array<float> tries = {0, JUNCTION_GAP, -JUNCTION_GAP, 2 * JUNCTION_GAP, -2 * JUNCTION_GAP};
				foreach (float shift : tries)
				{
					float candidate = Math.Clamp(bestS + shift, low, high);
					bool crowded = false;
					foreach (int b, int bp : branchOf)
					{
						if (bp == bestParent && Math.AbsFloat(branchAt[b] - candidate) < JUNCTION_GAP - 0.5)
							crowded = true;
					}

					if (!crowded)
					{
						at = candidate;
						break;
					}
				}

				vector leave = parentPath.At(at);
				vector tangent = parentPath.At(at + 2) - parentPath.At(Math.Max(at - 2, 0));
				tangent[1] = 0;
				if (tangent.Length() < 0.01)
					tangent = fromDir;
				else
					tangent = tangent * (1 / tangent.Length());

				vector side = Vector(tangent[2], 0, -tangent[0]);
				vector toward = target.m_vSocketPos - leave;
				toward[1] = 0;
				if (vector.Dot(side, toward) < 0)
					side = -side;

				float leadSide = Math.Min(SIDE, Flat(leave, target.m_vSocketPos) / 3);
				route = MakeRoute(api, cfg, "connect to " + target.m_sName, leave, side, leadSide, target);
				branchOf.Insert(bestParent);
				branchAt.Insert(at);
			}

			route.m_iPin = bestPin;
			paths.Insert(route);
		}

		if (paths.IsEmpty())
			return false;

		SP_TunnelSplinePath.Link(paths, api, 3);
		foreach (int n, SP_TunnelSplinePath linked : paths)
		{
			string role = "main";
			if (linked.m_iParent == -2)
				role = "NOT LINKED to the others";
			else if (linked.m_iParent >= 0)
				role = string.Format("branch off route %1 at %2 m", linked.m_iParent, Math.Round(linked.m_fParentS));

			Print(string.Format("SP_TunnelGen: route %1 '%2': %3 m, %4", n, linked.m_sName, Math.Round(linked.m_fLength), role));
		}

		return true;
	}
}
#endif
