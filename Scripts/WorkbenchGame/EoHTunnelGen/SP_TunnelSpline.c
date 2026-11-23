#ifdef WORKBENCH
//! A spline (or polyline) the generator follows: its curve in world space, sampled about every metre, how far along
//! each sample is, the height wanted there, and the spline's own points with what they ask for (SP_TunnelSplinePointData).

//! One spline point, or a junction the generator adds where a branch spline leaves
class SP_TunnelSplineMark
{
	int m_iAnchor = -1;		// the spline's point index; -1: added for a branch spline
	float m_fS;				// how far along the path
	vector m_vPos;			// world
	bool m_bHasData;
	ResourceName m_sPiece;
	int m_iKind;
	bool m_bNoTurns;
	int m_iChild = -1;		// the branch spline that leaves here (added junctions only)

	bool HasPiece()
	{
		return !m_sPiece.IsEmpty() || m_iKind != SP_TunnelSplineKind.ANY;
	}

	string Describe()
	{
		string what = SP_TunnelSplineKind.Name(m_iKind);
		if (!m_sPiece.IsEmpty())
			what = m_sPiece;

		if (m_iAnchor < 0)
			return "added junction (" + what + ")";

		return string.Format("point %1 (%2)", m_iAnchor, what);
	}
}

class SP_TunnelSplinePath
{
	protected static const float STEP = 1.0;
	protected static const float ON_GROUND = 0.5;	// a sample this close under the ground (or over it) was drawn on it

	string m_sName;
	bool m_bClosed;
	ref array<vector> m_aCurve = {};			// as read (world), before sampling
	ref array<ref SP_TunnelSplineMark> m_aMarks = {};

	ref array<vector> m_aPoints = {};			// sampled, world
	ref array<float> m_aS = {};				// along, on the ground plane
	ref array<bool> m_aOnGround = {};			// drawn on the ground: keep the usual earth cover there
	float m_fLength;

	int m_iParent = -1;		// the path this one branches off (-1: the main one, -2: not linked)
	float m_fParentS;
	bool m_bClaimed;			// a growing layout has started down it

	//------------------------------------------------------------------------------------------------
	//! Turned round: the last point first
	void Reverse()
	{
		array<vector> curve = {};
		for (int i = m_aCurve.Count() - 1; i >= 0; i--)
		{
			curve.Insert(m_aCurve[i]);
		}

		m_aCurve = curve;
		array<ref SP_TunnelSplineMark> marks = {};
		for (int m = m_aMarks.Count() - 1; m >= 0; m--)
		{
			marks.Insert(m_aMarks[m]);
		}

		m_aMarks = marks;
	}

	//------------------------------------------------------------------------------------------------
	vector First()
	{
		return m_aCurve[0];
	}

	//------------------------------------------------------------------------------------------------
	vector Last()
	{
		return m_aCurve[m_aCurve.Count() - 1];
	}

	//------------------------------------------------------------------------------------------------
	//! Samples the curve every metre, measures it, and finds each point's place along it
	void Build(WorldEditorAPI api)
	{
		m_aPoints.Clear();
		m_aS.Clear();
		m_aOnGround.Clear();
		float along = 0;
		for (int i = 0; i < m_aCurve.Count(); i++)
		{
			vector b = m_aCurve[i];
			if (i == 0)
			{
				AddSample(api, b, 0);
				continue;
			}

			vector a = m_aCurve[i - 1];
			float span = vector.DistanceXZ(a, b);
			if (span < 0.001)
				continue;

			int steps = Math.Max(1, Math.Ceil(span / STEP));
			for (int k = 1; k <= steps; k++)
			{
				// (k / steps would be a whole number)
				float t = k;
				t = t / steps;
				AddSample(api, a + (b - a) * t, along + span * t);
			}

			along += span;
		}

		m_fLength = along;

		// Each point's place: the nearest sample, searched on from the point before
		int from = 0;
		foreach (SP_TunnelSplineMark mark : m_aMarks)
		{
			if (mark.m_iAnchor < 0)
				continue;

			int best = from;
			float bestDist = 100000;
			for (int j = from; j < m_aPoints.Count(); j++)
			{
				float d = vector.Distance(m_aPoints[j], mark.m_vPos);
				if (d < bestDist)
				{
					bestDist = d;
					best = j;
				}
			}

			mark.m_fS = m_aS[best];
			from = best;
		}
	}

	//------------------------------------------------------------------------------------------------
	protected void AddSample(WorldEditorAPI api, vector p, float along)
	{
		m_aPoints.Insert(p);
		m_aS.Insert(along);
		float ground = api.GetTerrainSurfaceY(p[0], p[2]);
		m_aOnGround.Insert(p[1] > ground - ON_GROUND);
	}

	//------------------------------------------------------------------------------------------------
	//! The sample at or just before this distance along
	protected int IndexAt(float s)
	{
		int last = m_aS.Count() - 1;
		if (last <= 0 || s <= 0)
			return 0;

		if (s >= m_fLength)
			return last;

		int index = Math.Min(Math.Floor(s / STEP), last);
		while (index > 0 && m_aS[index] > s)
		{
			index--;
		}

		while (index < last && m_aS[index + 1] <= s)
		{
			index++;
		}

		return index;
	}

	//------------------------------------------------------------------------------------------------
	//! The point this far along (clamped to the ends)
	vector At(float s)
	{
		int i = IndexAt(s);
		if (i >= m_aPoints.Count() - 1)
			return m_aPoints[m_aPoints.Count() - 1];

		float span = m_aS[i + 1] - m_aS[i];
		float t = 0;
		if (span > 0.0001)
			t = Math.Clamp((s - m_aS[i]) / span, 0, 1);

		return m_aPoints[i] + (m_aPoints[i + 1] - m_aPoints[i]) * t;
	}

	//------------------------------------------------------------------------------------------------
	//! The height wanted for the tunnel's centre line (its sockets) this far along
	float WantY(float s)
	{
		vector p = At(s);
		return p[1];
	}

	//------------------------------------------------------------------------------------------------
	//! Drawn on the ground here: the tunnel keeps the usual earth cover instead of the spline's height
	bool OnGround(float s)
	{
		int i = IndexAt(s);
		if (i < m_aOnGround.Count() - 1 && s - m_aS[i] > 0.5 * (m_aS[i + 1] - m_aS[i]))
			i++;

		return m_aOnGround[i];
	}

	//------------------------------------------------------------------------------------------------
	//! Nearest place on the path to a position, on the ground plane, looking only from a little behind fromS to ahead
	//! of it (so a path that comes back near itself isn't jumped along). Returns how far along; lateral: how far off.
	float Project(vector pos, float fromS, float ahead, out float lateral)
	{
		lateral = 100000;
		float bestS = fromS;
		int count = m_aPoints.Count();
		for (int i = 0; i < count - 1; i++)
		{
			if (m_aS[i + 1] < fromS - 5)
				continue;

			if (m_aS[i] > fromS + ahead)
				break;

			vector a = m_aPoints[i];
			vector b = m_aPoints[i + 1];
			float abx = b[0] - a[0];
			float abz = b[2] - a[2];
			float len2 = abx * abx + abz * abz;
			float t = 0;
			if (len2 > 0.000001)
				t = Math.Clamp(((pos[0] - a[0]) * abx + (pos[2] - a[2]) * abz) / len2, 0, 1);

			float qx = a[0] + abx * t - pos[0];
			float qz = a[2] + abz * t - pos[2];
			float d = Math.Sqrt(qx * qx + qz * qz);
			if (d < lateral)
			{
				lateral = d;
				bestS = m_aS[i] + (m_aS[i + 1] - m_aS[i]) * t;
			}
		}

		if (count == 1)
		{
			lateral = vector.DistanceXZ(pos, m_aPoints[0]);
			bestS = 0;
		}

		return bestS;
	}

	//------------------------------------------------------------------------------------------------
	//! Nearest place anywhere on the path
	float ProjectAll(vector pos, out float lateral)
	{
		return Project(pos, 0, m_fLength + 10, lateral);
	}

	//------------------------------------------------------------------------------------------------
	int CountPieces()
	{
		int n = 0;
		foreach (SP_TunnelSplineMark mark : m_aMarks)
		{
			if (mark.HasPiece())
				n++;
		}

		return n;
	}

	//------------------------------------------------------------------------------------------------
	//! Puts the paths together: paths[0] is the main one (already built, its start at the start piece). Every other one
	//! that starts (or ends: then it's turned round) near a path already linked becomes a branch of it, with a junction
	//! added on that path where it leaves (unless a point near there already asks for a piece).
	static void Link(notnull array<ref SP_TunnelSplinePath> paths, WorldEditorAPI api, float radius)
	{
		if (paths.IsEmpty())
			return;

		paths[0].m_iParent = -1;
		for (int p = 1; p < paths.Count(); p++)
		{
			paths[p].m_iParent = -2;
		}

		bool linkedOne = true;
		while (linkedOne)
		{
			linkedOne = false;
			foreach (int c, SP_TunnelSplinePath child : paths)
			{
				if (child.m_iParent != -2)
					continue;

				int bestParent = -1;
				float bestDist = radius;
				bool bestReversed = false;
				foreach (int q, SP_TunnelSplinePath parent : paths)
				{
					if (q == c || parent.m_iParent == -2)
						continue;

					float dFirst;
					parent.ProjectAll(child.First(), dFirst);
					float dLast;
					parent.ProjectAll(child.Last(), dLast);
					if (dFirst < bestDist)
					{
						bestDist = dFirst;
						bestParent = q;
						bestReversed = false;
					}

					if (dLast < bestDist)
					{
						bestDist = dLast;
						bestParent = q;
						bestReversed = true;
					}
				}

				if (bestParent < 0)
					continue;

				if (bestReversed)
				{
					child.Reverse();
					child.Build(api);
				}

				child.m_iParent = bestParent;
				float unused;
				child.m_fParentS = paths[bestParent].ProjectAll(child.First(), unused);
				linkedOne = true;
			}
		}

		// A junction on the parent where each branch leaves, unless it's right at the start or a point there asks for a piece
		foreach (int b, SP_TunnelSplinePath branch : paths)
		{
			if (branch.m_iParent < 0 || branch.m_fParentS < 3)
				continue;

			SP_TunnelSplinePath on = paths[branch.m_iParent];
			bool asked = false;
			foreach (SP_TunnelSplineMark existing : on.m_aMarks)
			{
				if (existing.HasPiece() && Math.AbsFloat(existing.m_fS - branch.m_fParentS) < 4)
					asked = true;
			}

			if (asked)
				continue;

			SP_TunnelSplineMark junction = new SP_TunnelSplineMark();
			junction.m_iKind = SP_TunnelSplineKind.JUNCTION;
			junction.m_fS = branch.m_fParentS;
			junction.m_vPos = on.At(branch.m_fParentS);
			junction.m_iChild = b;
			int at = on.m_aMarks.Count();
			for (int m = 0; m < on.m_aMarks.Count(); m++)
			{
				if (on.m_aMarks[m].m_fS > junction.m_fS)
				{
					at = m;
					break;
				}
			}

			on.m_aMarks.InsertAt(junction, at);
		}
	}
}
#endif
