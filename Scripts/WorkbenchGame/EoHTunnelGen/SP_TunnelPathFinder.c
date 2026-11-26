#ifdef WORKBENCH
//! A random chain of pieces from one opening to another, for the hover tool's shift+click path.
//!
//! A weighted A* over the two-opening dug pieces of the kit (straights, curves, turns, doglegs, slopes; transitions when the two
//! openings differ in size). Cave openings get an adapter first (the hover tool does that). Every run weighs the moves differently, so the same two openings
//! get a different path each time, and pieces with the same geometry (_A, standard, _C) are picked at random.
//! Neither of the two openings' pieces ever moves. Pieces only turn in 5 degree steps and climb a slope piece at a time, so a chain
//! rarely ends exactly: what it misses by is spread over all its joints (a few cm and a fraction of a degree each, which the
//! sleeves cover). A chain counts when every joint stays within the given gap, step and wedge.

//! One step the search can take: from an opening, travelling along +Z, to the far opening of a piece
class SP_PathMove
{
	int m_iFrom;		// size of the opening it is joined by
	int m_iTo;			// size of the far opening
	vector m_vEnd;		// the far opening, seen from the near one
	float m_fTurn;		// how far the heading turns
	float m_fCost;
	ref array<int> m_aPieces = {};		// the pieces with this geometry
	ref array<int> m_aSockets = {};		// and which of their openings is the near one
}

class SP_PathNode
{
	vector m_vPos;			// the open end
	float m_fYaw;			// the direction out of it
	int m_iSize;
	float m_fCost;
	SP_PathNode m_Parent;	// held by the search's node list
	int m_iMove = -1;
	int m_iDepth;			// pieces so far
	ref array<vector> m_aSamples = {};	// points along the piece that led here
}

//! A piece of the found path, as it is to be placed
class SP_PathStep
{
	int m_iPiece;
	int m_iSocket;			// the opening it is joined by (the other one leads on)
	vector m_vPos;
	float m_fYaw;
}

//! A room or junction in the world: a box nothing may run through
class SP_PathBox
{
	vector m_vPos;
	float m_fYaw;
	vector m_vMin;
	vector m_vMax;
}

class SP_TunnelPathFinder
{
	protected static const float CELL = 3.0;			// of the grid the world's obstacle points are kept in
	protected static const float CLEAR_SQ = 4.4;		// two tunnels' middles closer than this (squared, in plan) collide
	protected static const float CLEAR_Y = 2.4;
	protected static const float END_FREE = 3.0;		// obstacles this near either end are the pieces being joined
	protected static const float HEURISTIC = 1.6;		// more than 1: reaches the goal sooner, with less tidy paths
	protected static const int AFTER_FOUND = 600;		// nodes looked at after the first path, for one that ends nearer
	protected static const float NEAR_ENOUGH = 2.5;	// a chain ending this close is checked for what its joints would have to take
	protected static const int MAX_MS = 4000;		// per attempt: the editor waits while it searches
	protected static const float ROOF_ABOVE = 2.2;		// a tunnel's outside, above its opening's point
	protected static const float COVER_WEIGHT = 0.25;	// small: a preference, it must not drown the distance left

	// the result of Find
	ref array<ref SP_PathStep> m_aSteps = {};
	float m_fGapFlat;		// per joint: what each has to take sideways / along
	float m_fGapHeight;		// as a step
	float m_fGapYaw;		// and as a wedge, degrees (signed: how much each joint turns)
	float m_fNearest;		// when nothing was found: the closest any chain came, metres
	float m_fLength;
	int m_iNodes;

	protected SP_TunnelCatalog m_Catalog;
	protected WorldEditorAPI m_API;		// null: don't care how deep the path runs
	protected ref RandomGenerator m_Rand = new RandomGenerator();
	protected ref array<ref SP_PathMove> m_aMoves = {};
	protected ref map<int, int> m_Grid = new map<int, int>();
	protected ref array<ref array<vector>> m_aCells = {};
	protected ref array<ref SP_PathBox> m_aBoxes = {};
	protected ref array<ref SP_PathNode> m_aNodes = {};
	protected ref array<int> m_aHeap = {};		// node numbers, smallest priority first
	protected ref array<float> m_aPriority = {};
	protected vector m_vStart;
	protected vector m_vGoal;
	protected float m_fGoalYaw;
	protected float m_fStartYaw;

	//------------------------------------------------------------------------------------------------
	void SP_TunnelPathFinder(SP_TunnelCatalog catalog, WorldEditorAPI api, int seed)
	{
		m_Catalog = catalog;
		m_API = api;
		m_Rand.SetSeed(seed);
	}

	//------------------------------------------------------------------------------------------------
	//! The pieces the path may use: the dug ones (the cave passes are too few and big to steer with); transitions only when asked for
	void BuildMoves(bool transitions)
	{
		m_aMoves.Clear();
		map<string, int> known = new map<string, int>();
		foreach (int p, SP_TunnelPieceDef def : m_Catalog.m_aPieces)
		{
			if (def.m_aSockets.Count() != 2 || def.m_sName.Contains("Adapter") || def.m_sName.Contains("Brk_"))
				continue;

			bool transition = def.m_iKind == SP_TunnelKind.TRANSITION;
			if (transition)
			{
				if (!transitions)
					continue;
			}
			else
			{
				if (def.m_iKind != SP_TunnelKind.STRAIGHT && def.m_iKind != SP_TunnelKind.TURN && def.m_iKind != SP_TunnelKind.BEND && def.m_iKind != SP_TunnelKind.HUMP && def.m_iKind != SP_TunnelKind.SLOPE && def.m_iKind != SP_TunnelKind.UPTURN)
					continue;

				if (SP_TunnelCatalog.ThemeOf(def.m_sName) == SP_TunnelTheme.CAVE)
					continue;
			}

			for (int e = 0; e < 2; e++)
			{
				SP_TunnelSocketDef near = def.m_aSockets[e];
				SP_TunnelSocketDef far = def.m_aSockets[1 - e];
				if (near.m_iRole != SP_TunnelRole.PATH || far.m_iRole != SP_TunnelRole.PATH)
					continue;

				vector pos;
				float yaw;
				// as seen from an opening that leads along +Z (Attach takes the open end's outward direction, i.e. the way travelled)
				SP_TunnelGrower.Attach(vector.Zero, "0 0 1", near, pos, yaw);
				vector reach = pos + SP_TunnelGrower.Rot(far.m_vPos, yaw);
				float turn = SP_TunnelConnect.Wrap(SP_TunnelGrower.YawOf(SP_TunnelGrower.Rot(far.m_vDir, yaw)));
				int kx = Math.Round(reach[0] * 10);
				int ky = Math.Round(reach[1] * 10);
				int kz = Math.Round(reach[2] * 10);
				int kt = Math.Round(turn);
				string key = string.Format("%1:%2:%3:%4:%5:%6", near.m_iSize, far.m_iSize, kx, ky, kz, kt);
				int index;
				if (!known.Find(key, index))
				{
					SP_PathMove move = new SP_PathMove();
					move.m_iFrom = near.m_iSize;
					move.m_iTo = far.m_iSize;
					move.m_vEnd = reach;
					move.m_fTurn = turn;
					move.m_fCost = Math.Max(Math.Sqrt(reach[0] * reach[0] + reach[2] * reach[2]), 0.5);
					if (def.m_iKind == SP_TunnelKind.BEND)
						move.m_fCost += 0.5;

					index = m_aMoves.Insert(move);
					known.Insert(key, index);
				}

				SP_PathMove same = m_aMoves[index];
				if (same.m_aPieces.Find(p) < 0)
				{
					same.m_aPieces.Insert(p);
					same.m_aSockets.Insert(e);
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Points along a piece's middle, from an opening to another: a curve leaving along dirA and arriving along dirB
	static void Along(vector a, vector dirA, vector b, vector dirB, notnull array<vector> points)
	{
		float reach = vector.DistanceXZ(a, b);
		vector m0 = dirA * reach;
		vector m1 = dirB * reach;
		int n = Math.Max(2, Math.Floor(reach / 1.2) + 1);
		for (int i = 1; i <= n; i++)
		{
			float t = i;
			t = t / n;
			float t2 = t * t;
			float t3 = t2 * t;
			points.Insert(a * (2 * t3 - 3 * t2 + 1) + m0 * (t3 - 2 * t2 + t) + b * (-2 * t3 + 3 * t2) + m1 * (t3 - t2));
		}
	}

	//------------------------------------------------------------------------------------------------
	protected int CellKey(int cx, int cz)
	{
		return (cx + 8192) * 32768 + cz + 8192;		// numbers: this is asked millions of times
	}

	//------------------------------------------------------------------------------------------------
	void AddObstaclePoint(vector point)
	{
		int cx = Math.Floor(point[0] / CELL);
		int cz = Math.Floor(point[2] / CELL);
		int key = CellKey(cx, cz);
		int index;
		if (!m_Grid.Find(key, index))
		{
			array<vector> cell = {};
			index = m_aCells.Insert(cell);
			m_Grid.Insert(key, index);
		}

		m_aCells[index].Insert(point);
	}

	//------------------------------------------------------------------------------------------------
	void AddObstacleBox(SP_TunnelPieceDef def, vector pos, float yaw)
	{
		SP_PathBox box = new SP_PathBox();
		box.m_vPos = pos;
		box.m_fYaw = yaw;
		box.m_vMin = def.m_vMin;
		box.m_vMax = def.m_vMax;
		m_aBoxes.Insert(box);
	}

	//------------------------------------------------------------------------------------------------
	protected bool Blocked(vector point, SP_PathNode from)
	{
		// the path itself, but for the piece just before this one (that one it joins)
		SP_PathNode earlier = from.m_Parent;
		while (earlier)
		{
			foreach (vector own : earlier.m_aSamples)
			{
				float ox = point[0] - own[0];
				float oz = point[2] - own[2];
				if (ox * ox + oz * oz < CLEAR_SQ && Math.AbsFloat(point[1] - own[1]) < CLEAR_Y)
					return true;
			}

			earlier = earlier.m_Parent;
		}

		if (vector.Distance(point, m_vStart) < END_FREE || vector.Distance(point, m_vGoal) < END_FREE)
			return false;

		int cx = Math.Floor(point[0] / CELL);
		int cz = Math.Floor(point[2] / CELL);
		for (int dx = -1; dx <= 1; dx++)
		{
			for (int dz = -1; dz <= 1; dz++)
			{
				int index;
				if (!m_Grid.Find(CellKey(cx + dx, cz + dz), index))
					continue;

				foreach (vector other : m_aCells[index])
				{
					float wx = point[0] - other[0];
					float wz = point[2] - other[2];
					if (wx * wx + wz * wz < CLEAR_SQ && Math.AbsFloat(point[1] - other[1]) < CLEAR_Y)
						return true;
				}
			}
		}

		foreach (SP_PathBox box : m_aBoxes)
		{
			vector local = SP_TunnelGrower.Rot(point - box.m_vPos, -box.m_fYaw);
			if (local[0] > box.m_vMin[0] - 0.8 && local[0] < box.m_vMax[0] + 0.8 && local[2] > box.m_vMin[2] - 0.8 && local[2] < box.m_vMax[2] + 0.8 && local[1] > box.m_vMin[1] - 1 && local[1] < box.m_vMax[1] + 1)
				return true;
		}

		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! Is there earth over this spot?
	protected bool Covered(vector point)
	{
		return point[1] + ROOF_ABOVE < m_API.GetTerrainSurfaceY(point[0], point[2]);
	}

	//------------------------------------------------------------------------------------------------
	//! Extra cost for running too near the surface or above it (away from the two ends, which may be at the surface)
	protected float Shallow(vector point)
	{
		if (!m_API)
			return 0;

		if (vector.DistanceXZ(point, m_vStart) < 6 || vector.DistanceXZ(point, m_vGoal) < 6)
			return 0;

		float missing = point[1] + ROOF_ABOVE - m_API.GetTerrainSurfaceY(point[0], point[2]);
		if (missing <= 0)
			return 0;

		return Math.Min(missing, 4) * COVER_WEIGHT;
	}

	//------------------------------------------------------------------------------------------------
	//! What is left to the goal, roughly in metres
	protected float Remaining(vector pos, float yaw)
	{
		float flat = vector.DistanceXZ(pos, m_vGoal);
		float height = Math.AbsFloat(m_vGoal[1] - pos[1]);
		float want = m_fGoalYaw;		// near the goal the heading has to match, further out it only has to point there
		if (flat > 7)
			want = SP_TunnelGrower.YawOf(m_vGoal - pos);

		return flat + 3 * height + Math.AbsFloat(SP_TunnelConnect.Wrap(want - yaw)) / 30;
	}

	//------------------------------------------------------------------------------------------------
	protected void Push(int node, float priority)
	{
		m_aHeap.Insert(node);
		m_aPriority.Insert(priority);
		int i = m_aHeap.Count() - 1;
		while (i > 0)
		{
			int up = (i - 1) / 2;
			if (m_aPriority[up] <= m_aPriority[i])
				break;

			m_aHeap.SwapItems(up, i);
			m_aPriority.SwapItems(up, i);
			i = up;
		}
	}

	//------------------------------------------------------------------------------------------------
	protected int Pop()
	{
		int top = m_aHeap[0];
		int last = m_aHeap.Count() - 1;
		m_aHeap.SwapItems(0, last);
		m_aPriority.SwapItems(0, last);
		m_aHeap.Remove(last);
		m_aPriority.Remove(last);
		int i = 0;
		while (true)
		{
			int least = i;
			int left = i * 2 + 1;
			int right = i * 2 + 2;
			if (left < last && m_aPriority[left] < m_aPriority[least])
				least = left;

			if (right < last && m_aPriority[right] < m_aPriority[least])
				least = right;

			if (least == i)
				break;

			m_aHeap.SwapItems(least, i);
			m_aPriority.SwapItems(least, i);
			i = least;
		}

		return top;
	}

	//------------------------------------------------------------------------------------------------
	//! A chain of moves with what it misses the goal by spread over its joints: the turn first (every joint the same wedge), then
	//! the position that is left (each piece shifted a share more than the one before). steps: filled when given
	protected void Relax(notnull array<int> chain, out float gapFlat, out float gapHeight, out float wedge)
	{
		int joints = chain.Count() + 1;
		float yaw = m_fStartYaw;
		foreach (int m : chain)
		{
			yaw += m_aMoves[m].m_fTurn;
		}

		wedge = SP_TunnelConnect.Wrap(m_fGoalYaw - yaw) / joints;
		vector pos = m_vStart;
		yaw = m_fStartYaw;
		foreach (int n : chain)
		{
			yaw += wedge;
			pos = pos + SP_TunnelGrower.Rot(m_aMoves[n].m_vEnd, yaw);
			yaw += m_aMoves[n].m_fTurn;
		}

		vector miss = m_vGoal - pos;
		gapFlat = Math.Sqrt(miss[0] * miss[0] + miss[2] * miss[2]) / joints;
		gapHeight = Math.AbsFloat(miss[1]) / joints;
	}

	//------------------------------------------------------------------------------------------------
	protected void ChainOf(SP_PathNode last, int then, notnull array<int> chain)
	{
		chain.Clear();
		SP_PathNode node = last;
		while (node.m_Parent)
		{
			chain.InsertAt(node.m_iMove, 0);
			node = node.m_Parent;
		}

		chain.Insert(then);
	}

	//------------------------------------------------------------------------------------------------
	//! The safety net: every joint measured again from the poses the pieces are about to get and their own openings, not from the
	//! search's sums. Anything off: nothing is built
	protected bool Verify(float maxGap, float maxStep, float maxWedge)
	{
		vector openPos = m_vStart;
		float openYaw = m_fStartYaw;
		foreach (int i, SP_PathStep step : m_aSteps)
		{
			SP_TunnelPieceDef def = m_Catalog.m_aPieces[step.m_iPiece];
			SP_TunnelSocketDef near = def.m_aSockets[step.m_iSocket];
			SP_TunnelSocketDef far = def.m_aSockets[1 - step.m_iSocket];
			vector nearPos = step.m_vPos + SP_TunnelGrower.Rot(near.m_vPos, step.m_fYaw);
			float facing = SP_TunnelGrower.YawOf(SP_TunnelGrower.Rot(near.m_vDir, step.m_fYaw)) - openYaw - 180;
			if (!Joins(openPos, nearPos, facing, maxGap, maxStep, maxWedge, i))
				return false;

			openPos = step.m_vPos + SP_TunnelGrower.Rot(far.m_vPos, step.m_fYaw);
			openYaw = SP_TunnelGrower.YawOf(SP_TunnelGrower.Rot(far.m_vDir, step.m_fYaw));
		}

		// the last one against the target opening (which faces back, against the way travelled into it)
		return Joins(openPos, m_vGoal, m_fGoalYaw - openYaw, maxGap, maxStep, maxWedge, m_aSteps.Count());
	}

	//------------------------------------------------------------------------------------------------
	protected bool Joins(vector a, vector b, float angle, float maxGap, float maxStep, float maxWedge, int joint)
	{
		float gap = vector.DistanceXZ(a, b);
		float high = Math.AbsFloat(a[1] - b[1]);
		float off = Math.AbsFloat(SP_TunnelConnect.Wrap(angle));
		if (gap <= maxGap + 0.05 && high <= maxStep + 0.03 && off <= maxWedge + 0.5)
			return true;

		Print(string.Format("SP_TunnelPathFinder: BUG: joint %1 would be %2 m apart, %3 m in height, %4 degrees off. Nothing built.", joint, gap.ToString(-1, 2), high.ToString(-1, 2), Math.Round(off)), LogLevel.ERROR);
		return false;
	}

	//------------------------------------------------------------------------------------------------
	//! start / startYaw: the opening to grow from and the direction out of it. goal / goalYaw: where to arrive and the direction
	//! travelled on arriving (into the target opening). The three limits: what one joint may take. True: m_aSteps holds a path
	bool Find(vector start, float startYaw, int startSize, vector goal, float goalYaw, int goalSize, float maxGap, float maxStep, float maxWedge, int maxNodes)
	{
		m_vStart = start;
		m_vGoal = goal;
		m_fGoalYaw = goalYaw;
		m_fStartYaw = startYaw;
		if (m_API && (!Covered(start) || !Covered(goal)))
			m_API = null;		// an end at the surface (or a test above ground): depth says nothing

		m_aSteps.Clear();
		m_aNodes.Clear();
		m_aHeap.Clear();
		m_aPriority.Clear();
		m_fNearest = 100000;
		m_iNodes = 0;

		array<float> liking = {};		// this run's own weighting of the moves: why every path is different
		for (int j = 0; j < m_aMoves.Count(); j++)
		{
			liking.Insert(m_Rand.RandFloatXY(0.75, 1.5));
		}

		SP_PathNode first = new SP_PathNode();
		first.m_vPos = start;
		first.m_fYaw = startYaw;
		first.m_iSize = startSize;
		m_aNodes.Insert(first);
		Push(0, Remaining(start, startYaw) * HEURISTIC);

		map<string, float> reached = new map<string, float>();
		array<int> bestChain = {};
		array<int> chain = {};
		float bestScore = 100000;
		int foundAt = 0;
		int started = System.GetTickCount();
		while (!m_aHeap.IsEmpty() && m_iNodes < maxNodes)
		{
			SP_PathNode node = m_aNodes[Pop()];
			m_iNodes++;
			if (foundAt > 0 && m_iNodes - foundAt > AFTER_FOUND)
				break;

			if (System.GetTickCount() - started > MAX_MS)
				break;

			foreach (int m, SP_PathMove move : m_aMoves)
			{
				if (move.m_iFrom != node.m_iSize)
					continue;

				// a change of size only towards the target's
				if (move.m_iTo != move.m_iFrom && Math.AbsInt(move.m_iTo - goalSize) >= Math.AbsInt(move.m_iFrom - goalSize))
					continue;

				vector end = node.m_vPos + SP_TunnelGrower.Rot(move.m_vEnd, node.m_fYaw);
				float yaw = SP_TunnelConnect.Wrap(node.m_fYaw + move.m_fTurn);
				float missFlat = vector.DistanceXZ(end, goal);
				float missHeight = Math.AbsFloat(end[1] - goal[1]);
				float missYaw = Math.AbsFloat(SP_TunnelConnect.Wrap(yaw - goalYaw));
				int joints = node.m_iDepth + 2;
				bool near = move.m_iTo == goalSize && missFlat <= NEAR_ENOUGH && missHeight <= maxStep * joints && missYaw <= maxWedge * joints;
				if (move.m_iTo == goalSize)
					m_fNearest = Math.Min(m_fNearest, missFlat + missHeight);

				float cost = node.m_fCost + move.m_fCost * liking[m];
				if (m == node.m_iMove)
					cost += 0.6;

				int qx = Math.Round(end[0] * 2);
				int qy = Math.Round(end[1] * 2.5);
				int qz = Math.Round(end[2] * 2);
				int qt = Math.Round(yaw / 5);
				string key = string.Format("%1:%2:%3:%4:%5", qx, qy, qz, qt, move.m_iTo);
				float known;
				if (!near && reached.Find(key, known) && known <= cost)
					continue;

				vector dirA = SP_TunnelGrower.Rot("0 0 1", node.m_fYaw);
				vector dirB = SP_TunnelGrower.Rot("0 0 1", yaw);
				array<vector> points = {};
				Along(node.m_vPos, dirA, end, dirB, points);
				bool collides = false;
				float shallow = 0;
				foreach (vector point : points)
				{
					if (Blocked(point, node))
					{
						collides = true;
						break;
					}

					shallow += Shallow(point);
				}

				if (collides)
					continue;

				if (near)
				{
					ChainOf(node, m, chain);
					float gapFlat;
					float gapHeight;
					float wedge;
					Relax(chain, gapFlat, gapHeight, wedge);
					if (gapFlat <= maxGap && gapHeight <= maxStep && Math.AbsFloat(wedge) <= maxWedge)
					{
						float score = gapFlat / maxGap + gapHeight / maxStep + Math.AbsFloat(wedge) / maxWedge;
						if (score < bestScore)
						{
							bestScore = score;
							bestChain.Copy(chain);
						}

						if (foundAt == 0)
							foundAt = m_iNodes;

						continue;
					}

					if (reached.Find(key, known) && known <= cost)
						continue;
				}

				SP_PathNode child = new SP_PathNode();
				child.m_vPos = end;
				child.m_fYaw = yaw;
				child.m_iSize = move.m_iTo;
				child.m_fCost = cost + shallow;
				child.m_Parent = node;
				child.m_iMove = m;
				child.m_iDepth = node.m_iDepth + 1;
				child.m_aSamples.Copy(points);
				reached.Set(key, cost);
				int number = m_aNodes.Insert(child);
				Push(number, child.m_fCost + Remaining(end, yaw) * HEURISTIC);
			}
		}

		if (bestChain.IsEmpty())
			return false;

		Collect(bestChain);
		if (!Verify(maxGap, maxStep, maxWedge))
			return false;

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! The chain of moves as pieces with their poses, start first, the miss spread over the joints (see Relax); of pieces with
	//! the same geometry one at random
	protected void Collect(notnull array<int> chain)
	{
		Relax(chain, m_fGapFlat, m_fGapHeight, m_fGapYaw);
		m_fLength = 0;
		vector pos = m_vStart;
		float yaw = m_fStartYaw;
		int previous = -1;
		foreach (int m : chain)
		{
			SP_PathMove move = m_aMoves[m];
			int count = move.m_aPieces.Count();
			int pick = Math.Min(count - 1, Math.Floor(m_Rand.RandFloat01() * count));
			if (count > 1 && move.m_aPieces[pick] == previous)
				pick = (pick + 1) % count;

			previous = move.m_aPieces[pick];
			SP_TunnelSocketDef socket = m_Catalog.m_aPieces[previous].m_aSockets[move.m_aSockets[pick]];
			yaw += m_fGapYaw;
			SP_PathStep placed = new SP_PathStep();
			placed.m_iPiece = previous;
			placed.m_iSocket = move.m_aSockets[pick];
			SP_TunnelGrower.Attach(pos, SP_TunnelGrower.Rot("0 0 1", yaw), socket, placed.m_vPos, placed.m_fYaw);
			m_aSteps.Insert(placed);
			pos = pos + SP_TunnelGrower.Rot(move.m_vEnd, yaw);
			yaw += move.m_fTurn;
			m_fLength += move.m_fCost;
		}

		vector miss = m_vGoal - pos;
		int joints = chain.Count() + 1;
		foreach (int i, SP_PathStep step : m_aSteps)
		{
			float share = i + 1;
			step.m_vPos = step.m_vPos + miss * (share / joints);
		}
	}
}
#endif
